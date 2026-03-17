(ns persistence.similarity
  "Hierarchical and categorical similarity computation.
   Implements:
     - Hierarchical similarity: based on LCA (Lowest Common Ancestor) in category tree
     - Categorical similarity: Jaccard coefficient over shared categories
     - Cosine similarity: over weighted dimension vectors
   Results persisted to similarity_edges and entity_categories tables."
  (:require [next.jdbc          :as jdbc]
            [clojure.tools.logging :as log]
            [clojure.data.json  :as json]
            [persistence.categories :as cats]))

;; ── Jaccard (categorical) similarity ─────────────────────────────────────────

(defn jaccard
  "Jaccard similarity: |A ∩ B| / |A ∪ B|.
   Input: two sets of category gen_ids."
  [set-a set-b]
  (if (and (empty? set-a) (empty? set-b))
    1.0
    (let [intersection (count (clojure.set/intersection set-a set-b))
          union        (count (clojure.set/union set-a set-b))]
      (if (zero? union) 0.0
          (double (/ intersection union))))))

;; ── Cosine (weighted vector) similarity ──────────────────────────────────────

(defn cosine
  "Cosine similarity over weighted dimension vectors.
   Each entity is a map of dimension → score."
  [vec-a vec-b]
  (let [dims  (clojure.set/union (set (keys vec-a)) (set (keys vec-b)))
        dot   (reduce (fn [acc d]
                        (+ acc (* (get vec-a d 0.0) (get vec-b d 0.0))))
                      0.0 dims)
        mag-a (Math/sqrt (reduce + (map #(* % %) (vals vec-a))))
        mag-b (Math/sqrt (reduce + (map #(* % %) (vals vec-b))))]
    (if (or (zero? mag-a) (zero? mag-b))
      0.0
      (/ dot (* mag-a mag-b)))))

;; ── Hierarchical LCA similarity ───────────────────────────────────────────────

(defn ancestors
  "Return the set of ancestor gen_ids for a category (walking parent_id chain)."
  [ds cat-id]
  (loop [id cat-id, acc #{}]
    (if (nil? id)
      acc
      (let [row (first (jdbc/execute! ds
                         ["SELECT parent_id FROM categories WHERE gen_id=?" id]))]
        (recur (:categories/parent_id row) (conj acc id))))))

(defn hierarchical-sim
  "Similarity based on shared ancestors in the category tree.
   Normalised by max possible ancestor depth."
  [ds cat-id-a cat-id-b]
  (let [anc-a (ancestors ds cat-id-a)
        anc-b (ancestors ds cat-id-b)
        shared (count (clojure.set/intersection anc-a anc-b))
        total  (count (clojure.set/union anc-a anc-b))]
    (if (zero? total) 0.0 (double (/ shared total)))))

;; ── Entity category vectors ───────────────────────────────────────────────────

(defn entity-cat-set
  "Return the set of category gen_ids for an entity."
  [ds entity-id entity-type]
  (->> (jdbc/execute! ds
         ["SELECT category_id FROM entity_categories
            WHERE entity_id=? AND entity_type=?" entity-id entity-type])
       (map :entity_categories/category_id)
       set))

(defn entity-dim-vector
  "Return a map of dimension → max score for an entity."
  [ds entity-id entity-type]
  (let [scores (cats/score-entity ds entity-id entity-type)]
    (reduce (fn [acc {:keys [dimension score]}]
              (update acc dimension (fnil max 0.0) score))
            {}
            scores)))

;; ── Similarity entry point ────────────────────────────────────────────────────

(defn compute-similarity
  "Compute similarity between two entities using the given method.
   Methods: :hierarchical :categorical :cosine
   Returns a score in [0,1]."
  [ds src-id dst-id entity-type method]
  (case method
    :categorical
    (jaccard (entity-cat-set ds src-id entity-type)
             (entity-cat-set ds dst-id entity-type))

    :cosine
    (cosine (entity-dim-vector ds src-id entity-type)
            (entity-dim-vector ds dst-id entity-type))

    :hierarchical
    ;; Compare shared category ancestors
    (let [cats-a (entity-cat-set ds src-id entity-type)
          cats-b (entity-cat-set ds dst-id entity-type)
          pairs  (for [a cats-a b cats-b] [a b])]
      (if (empty? pairs)
        0.0
        (->> pairs
             (map (fn [[a b]] (hierarchical-sim ds a b)))
             (apply max))))

    ;; Default fallback
    0.0))

;; ── Persist similarity edge ───────────────────────────────────────────────────

(defn persist-edge!
  "Write a similarity edge to similarity_edges table.
   Weight = 1 - similarity (lower = more similar, for Dijkstra)."
  [ds gen-id src-id dst-id similarity edge-type]
  (let [weight (- 1.0 (min 1.0 (max 0.0 similarity)))]
    (jdbc/execute! ds
      ["INSERT OR IGNORE INTO similarity_edges
          (gen_id, src_id, dst_id, weight, edge_type)
        VALUES (?,?,?,?,?)"
       gen-id src-id dst-id weight edge-type])
    (log/debug "Edge" gen-id "weight" weight "type" edge-type)
    {:gen_id gen-id :weight weight}))

;; ── Batch similarity across all lineage pairs ─────────────────────────────────

(defn compute-all-lineage-similarities!
  "Compute categorical similarity between all pairs of lineage records
   and persist edges. Called by Phase 5 of the GitHub Action."
  [ds]
  (let [ids (->> (jdbc/execute! ds ["SELECT gen_id FROM lineage ORDER BY created_at DESC LIMIT 50"])
                 (map :lineage/gen_id))]
    (doseq [[a b] (for [x ids y ids :when (not= x y)] [x y])]
      (let [sim   (compute-similarity ds a b "lineage" :categorical)
            eid   (str "sim-" (subs a 0 6) "-" (subs b 0 6))]
        (when (> sim 0)
          (persist-edge! ds eid a b sim "similarity"))))))
