(ns singine.persistence.core
  "Singine persistence JVM entry point.
   Modes: categorise | similarity | status
   Reads SINGINE_DB env var for SQLite path."
  (:require [clojure.tools.cli    :refer [parse-opts]]
            [clojure.tools.logging :as log]
            [clojure.data.json    :as json]
            [next.jdbc            :as jdbc]
            [next.jdbc.result-set :as rs]
            [persistence.categories :as cats]
            [persistence.similarity :as sim])
  (:gen-class))

(def cli-options
  [["-m" "--mode MODE"   "Run mode: categorise|similarity|status"
    :default "status"]
   ["-d" "--db PATH"     "SQLite DB path"
    :default (or (System/getenv "SINGINE_DB") "singine.db")]
   ["-h" "--help"]])

(defn make-ds [db-path]
  (jdbc/get-datasource
   {:dbtype   "sqlite"
    :dbname   db-path
    :read-only false}))

(defmulti run-mode (fn [mode _ds _opts] (keyword mode)))

(defmethod run-mode :status [_ ds _opts]
  (let [tables (jdbc/execute! ds
                 ["SELECT name FROM sqlite_master WHERE type='table'"]
                 {:builder-fn rs/as-unqualified-maps})
        n      (count tables)]
    (println (json/write-str {:status "ok" :tables n :engine "singine-persistence-clj"}))))

(defmethod run-mode :categorise [_ ds _opts]
  (log/info "Bootstrapping categories and scoring all lineage entities")
  (cats/bootstrap-categories! ds)
  (let [lineage (jdbc/execute! ds ["SELECT gen_id FROM lineage"]
                               {:builder-fn rs/as-unqualified-maps})]
    (doseq [{:keys [gen_id]} lineage]
      (let [scores (cats/score-entity ds gen_id "lineage")]
        (when (seq scores)
          (log/info "Entity" gen_id "scores:" (count scores) "categories")
          ;; Persist top score as entity_category
          (let [{:keys [category_id score validated]} (first scores)
                ec-id (str "ec-" (subs gen_id 0 6))]
            (jdbc/execute! ds
              ["INSERT OR IGNORE INTO entity_categories
                  (gen_id, entity_id, entity_type, category_id, score, algorithm, validated)
                VALUES (?,?,?,?,?,?,?)"
               ec-id gen_id "lineage" category_id score "hierarchical"
               (if validated 1 0)])))))
    (println (json/write-str {:categorised (count lineage)}))))

(defmethod run-mode :similarity [_ ds _opts]
  (log/info "Computing lineage similarity edges")
  (sim/compute-all-lineage-similarities! ds)
  (println (json/write-str {:status "similarity-edges-computed"})))

(defmethod run-mode :default [mode _ _]
  (println (json/write-str {:error (str "Unknown mode: " mode)}))
  (System/exit 1))

(defn -main [& args]
  (let [{:keys [options errors]} (parse-opts args cli-options)]
    (when errors
      (doseq [e errors] (println e))
      (System/exit 1))
    (let [ds (make-ds (:db options))]
      (log/info "Singine persistence JVM — mode:" (:mode options) "db:" (:db options))
      (run-mode (:mode options) ds options))))
