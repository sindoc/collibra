(ns persistence.categories
  "Multi-dimensional category model with Boolean algebra constraints.
   Implements reification (making abstract categories concrete records)
   and deification (elevating to first-class validated governance objects).

   Dimensions: main · primary · secondary · n_linear · relational · boolean · temporal

   Boolean algebra over categories:
     (AND cat-a cat-b)  → intersection (both must match)
     (OR  cat-a cat-b)  → union        (either matches)
     (NOT cat-a)        → complement   (must not match)"
  (:require [clojure.spec.alpha :as s]
            [clojure.string :as str]
            [clojure.tools.logging :as log]
            [next.jdbc :as jdbc]
            [clojure.data.json :as json]))

;; ── Specs (validated algorithms) ─────────────────────────────────────────────

(s/def ::gen_id   string?)
(s/def ::name     string?)
(s/def ::urn      (s/and string? #(str/starts-with? % "urn:singine:cat:")))
(s/def ::dimension #{:main :primary :secondary :n_linear :relational :boolean :temporal})
(s/def ::weight   (s/and number? #(<= 0.0 % 1.0)))
(s/def ::validated boolean?)
(s/def ::bool_expr (s/nilable string?))

(s/def ::category
  (s/keys :req-un [::gen_id ::name ::urn ::dimension ::weight ::validated]
          :opt-un [::bool_expr ::parent_id]))

;; ── Boolean algebra evaluator ─────────────────────────────────────────────────

(defn- bool-and
  "Returns true if entity belongs to ALL given categories."
  [entity-cats & cat-ids]
  (every? (set entity-cats) cat-ids))

(defn- bool-or
  "Returns true if entity belongs to ANY of the given categories."
  [entity-cats & cat-ids]
  (some (set entity-cats) cat-ids))

(defn- bool-not
  "Returns true if entity does NOT belong to the given category."
  [entity-cats cat-id]
  (not ((set entity-cats) cat-id)))

(defn evaluate-bool-expr
  "Evaluate a boolean algebra expression string against entity's category IDs.
   Supported syntax: AND, OR, NOT, parentheses (lisp-style).
   Example: '(AND main primary)' '(OR secondary n_linear)' '(NOT boolean)'"
  [expr entity-cat-ids]
  (when expr
    (let [tokens (-> expr
                     (str/replace #"[()]" "")
                     str/trim
                     (str/split #"\s+"))]
      (case (first tokens)
        "AND" (apply bool-and entity-cat-ids (rest tokens))
        "OR"  (apply bool-or  entity-cat-ids (rest tokens))
        "NOT" (bool-not entity-cat-ids (second tokens))
        false))))

;; ── Reification ───────────────────────────────────────────────────────────────
;; Reification: convert abstract dimension keyword → concrete category record

(defrecord Category [gen_id name urn dimension weight validated bool_expr parent_id])

(defn reify-dimension
  "Reify a dimension keyword into a Category record.
   This is the 'making concrete' step — input: dimension keyword, output: Category."
  [dimension & {:keys [gen_id weight bool_expr parent_id]
                :or   {weight 1.0 bool_expr nil parent_id nil}}]
  {:pre [(s/valid? ::dimension dimension)]}
  (let [dim-str (name dimension)
        id      (or gen_id (str "cat-" dim-str))]
    (map->Category
     {:gen_id    id
      :name      (str/capitalize dim-str)
      :urn       (str "urn:singine:cat:" dim-str)
      :dimension dimension
      :weight    weight
      :validated true
      :bool_expr bool_expr
      :parent_id parent_id})))

;; ── Deification ───────────────────────────────────────────────────────────────
;; Deification: elevate a Category to a first-class validated governance object
;; with spec validation, URN addressability, and DB persistence.

(defn deify-category
  "Deify a category: validate with spec, assign URN, persist to DB.
   Returns the deified category map with :status :deified."
  [ds category]
  (if-not (s/valid? ::category category)
    (do
      (log/error "Category spec validation failed:"
                 (s/explain-str ::category category))
      (assoc category :status :invalid))
    (do
      (jdbc/execute! ds
        ["INSERT OR IGNORE INTO categories
            (gen_id, name, urn, dimension, parent_id, bool_expr, weight, validated)
          VALUES (?,?,?,?,?,?,?,?)"
         (:gen_id    category)
         (:name      category)
         (:urn       category)
         (name (:dimension category))
         (:parent_id category)
         (:bool_expr category)
         (:weight    category)
         (if (:validated category) 1 0)])
      (log/info "Deified category" (:urn category))
      (assoc category :status :deified))))

;; ── Hierarchical constraints ──────────────────────────────────────────────────

(defn build-hierarchy
  "Build a parent→children map from the categories table.
   Returns a map of parent gen_id → seq of child Category records."
  [ds]
  (let [rows (jdbc/execute! ds ["SELECT gen_id,name,urn,dimension,parent_id,weight,validated
                                   FROM categories"])]
    (reduce (fn [acc row]
              (let [parent (:categories/parent_id row)]
                (if parent
                  (update acc parent conj
                          {:gen_id    (:categories/gen_id row)
                           :urn       (:categories/urn row)
                           :dimension (keyword (:categories/dimension row))
                           :weight    (:categories/weight row)})
                  acc)))
            {}
            rows)))

;; ── Multi-dimensional scoring ─────────────────────────────────────────────────

(defn score-entity
  "Score an entity against all categories using Boolean algebra + hierarchy.
   Returns a vector of {:category_id :score :dimension :validated} sorted by score desc."
  [ds entity-id entity-type]
  (let [assigned (jdbc/execute! ds
                   ["SELECT category_id,score FROM entity_categories
                      WHERE entity_id=? AND entity_type=?"
                    entity-id entity-type])
        cat-ids  (mapv :entity_categories/category_id assigned)
        cats     (jdbc/execute! ds ["SELECT gen_id,urn,dimension,weight,validated,bool_expr
                                       FROM categories"])]
    (->> cats
         (map (fn [c]
                (let [dim       (keyword (:categories/dimension c))
                      bool-ok   (evaluate-bool-expr
                                  (:categories/bool_expr c) cat-ids)
                      member?   ((set cat-ids) (:categories/gen_id c))
                      raw-score (:categories/weight c)
                      score     (cond
                                  member?  raw-score
                                  bool-ok  (* raw-score 0.5)
                                  :else    0.0)]
                  {:category_id (:categories/gen_id c)
                   :urn         (:categories/urn c)
                   :dimension   dim
                   :score       score
                   :validated   (= 1 (:categories/validated c))})))
         (filter #(> (:score %) 0))
         (sort-by :score >))))

;; ── Bootstrap: load all 7 dimensions ─────────────────────────────────────────

(defn bootstrap-categories!
  "Deify all standard dimensions into the database."
  [ds]
  (doseq [dim [:main :primary :secondary :n_linear :relational :boolean :temporal]]
    (deify-category ds (reify-dimension dim))))
