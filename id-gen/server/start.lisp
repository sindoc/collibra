;;;; id-gen server — Common Lisp HTTP API
;;;; Starts with SSH public key as first input to establish identity.
;;;; Offers contract ID generation services on dev platform (net/DMZ mode).
;;;;
;;;; Usage (SBCL):
;;;;   sbcl --script start.lisp -- <ssh-pub-key-string> [port] [mode]
;;;; or load interactively:
;;;;   (load "start.lisp")
;;;;   (id-gen:start-server :ssh-key "ssh-rsa AAAA..." :port 7331 :mode :net)

(defpackage :id-gen
  (:use :cl)
  (:export #:start-server #:stop-server #:*server-state*))

(in-package :id-gen)

;;; ─── server state ────────────────────────────────────────────────────────────
(defparameter *server-state*
  (list :running    nil
        :mode       :net          ; :net | :dmz
        :port       7331
        :ssh-key    nil
        :ssh-fp     nil           ; fingerprint derived from key
        :contracts  (list)
        :started-at nil))

;;; ─── SSH key fingerprint ─────────────────────────────────────────────────────
(defun ssh-fingerprint (pubkey-string)
  "Derive a short fingerprint token from an SSH public key string.
   In production: call ssh-keygen -lf; here: hash the key comment + prefix."
  (let* ((parts (remove "" (cl:split-sequence #\Space pubkey-string) :test #'string=))
         (comment (if (>= (length parts) 3) (third parts) "unknown"))
         (keytype (if (>= (length parts) 1) (first parts) "ssh-rsa"))
         ;; Simple stable hash of the base64 body for fingerprint display
         (b64    (if (>= (length parts) 2) (second parts) ""))
         (hval   (mod (reduce #'+ (map 'list #'char-code b64)) 999983))
         (fp     (format nil "~a:~8,'0x:~a" keytype hval comment)))
    fp))

;;; ─── governance: DMZ endpoint filter ────────────────────────────────────────
(defparameter *dmz-allowed-paths*
  '("/health" "/api/id/gen" "/api/contracts/list" "/api/progress"))

(defun dmz-allowed-p (path)
  (member path *dmz-allowed-paths* :test #'string=))

;;; ─── response helpers ────────────────────────────────────────────────────────
(defun json-response (code body)
  (format nil "HTTP/1.1 ~a~%Content-Type: application/json~%Access-Control-Allow-Origin: *~%~%~a"
          (case code (200 "200 OK") (403 "403 Forbidden") (404 "404 Not Found")
                     (500 "500 Internal Server Error") (otherwise "200 OK"))
          body))

(defun html-response (body)
  (format nil "HTTP/1.1 200 OK~%Content-Type: text/html~%~%~a" body))

(defun uuid-v4 ()
  "Generate a UUID v4 string using /proc/sys/kernel/random/uuid."
  (let ((path "/proc/sys/kernel/random/uuid"))
    (if (probe-file path)
        (with-open-file (f path) (read-line f nil "00000000-0000-0000-0000-000000000000"))
        (format nil "~8,'0x-~4,'0x-4~3,'0x-~4,'0x-~12,'0x"
                (random #xFFFFFFFF) (random #xFFFF) (random #xFFF)
                (logior #x8000 (random #x3FFF)) (random #xFFFFFFFFFFFF)))))

;;; ─── request router ──────────────────────────────────────────────────────────
(defun dispatch (path method body state)
  (let ((mode (getf state :mode :net)))
    ;; DMZ mode: block non-whitelisted endpoints
    (when (and (eq mode :dmz) (not (dmz-allowed-p path)))
      (return-from dispatch
        (json-response 403 (format nil "{\"error\":\"DMZ mode: ~a not allowed\"}" path))))

    (cond
      ;; Health check
      ((string= path "/health")
       (json-response 200
         (format nil "{\"status\":\"ok\",\"mode\":\"~a\",\"port\":~a,\"ssh_fp\":\"~a\"}"
                 mode (getf state :port) (or (getf state :ssh-fp) "none"))))

      ;; Generate a new contract ID
      ((and (string= path "/api/id/gen") (string= method "POST"))
       (let* ((ns      "c")
              (kind    "contract")
              (uid     (uuid-v4))
              (id      (format nil "~a.~a.~a" ns kind uid))
              (tag     (format nil "id-gen/~a" id))
              (ts      (get-universal-time))
              (entry   (list :id id :tag tag :created ts
                             :ssh-fp (getf state :ssh-fp))))
         (push entry (getf *server-state* :contracts))
         (json-response 200
           (format nil "{\"id\":\"~a\",\"tag\":\"~a\",\"namespace\":\"c\",\"kind\":\"~a\",\"created\":~a}"
                   id tag kind ts))))

      ;; List contracts
      ((string= path "/api/contracts/list")
       (let ((contracts (getf state :contracts)))
         (json-response 200
           (format nil "[~{~a~^,~}]"
             (mapcar (lambda (c)
                       (format nil "{\"id\":\"~a\",\"tag\":\"~a\"}"
                               (getf c :id "?") (getf c :tag "?")))
                     contracts)))))

      ;; Progress (returns JSON for UI progress bar)
      ((string= path "/api/progress")
       (json-response 200
         "{\"steps\":[\"INIT\",\"EXTRACT\",\"CLASSIFY\",\"RELATE\",\"CONSTRAIN\",\"VERBALIZE\",\"ALIGN\",\"CONTRACT\"],\"total\":7}"))

      ;; Namespace info
      ((string= path "/api/namespaces")
       (json-response 200
         "{\"c\":{\"description\":\"Collibra-privileged IDs\",\"prefix\":\"c.\"},\"a\":{\"description\":\"Reserved namespace A\",\"prefix\":\"a.\"},\"b\":{\"description\":\"Reserved namespace B\",\"prefix\":\"b.\"}}"))

      ;; SSH identity
      ((string= path "/api/identity")
       (json-response 200
         (format nil "{\"ssh_fp\":\"~a\",\"mode\":\"~a\"}"
                 (or (getf state :ssh-fp) "unset") mode)))

      ;; Equation solver (GET /api/eq?expr=x*2)
      ((string= path "/api/eq")
       (json-response 200 "{\"note\":\"Use POST /api/eq with body {\\\"expr\\\":\\\"x^2+1\\\",\\\"mode\\\":\\\"solve|latex|plot\\\"}\"}"))

      ;; Index / dashboard redirect
      ((or (string= path "/") (string= path ""))
       (html-response
         (format nil "<html><body><h2>id-gen server</h2><pre>mode: ~a~%fp:   ~a</pre><ul><li><a href='/health'>/health</a></li><li><a href='/api/contracts/list'>/api/contracts/list</a></li><li><a href='/api/namespaces'>/api/namespaces</a></li><li><a href='/api/progress'>/api/progress</a></li></ul></body></html>"
                 mode (or (getf state :ssh-fp) "none"))))

      (t (json-response 404 (format nil "{\"error\":\"not found\",\"path\":\"~a\"}" path))))))

;;; ─── TCP server (SBCL sb-bsd-sockets) ───────────────────────────────────────
(defun parse-request (request-str)
  "Parse a minimal HTTP request, return (method path body)."
  (let* ((lines (cl:split-sequence #\Newline request-str))
         (first-line (first lines))
         (parts (remove "" (cl:split-sequence #\Space first-line) :test #'string=))
         (method (if parts (first parts) "GET"))
         (raw-path (if (>= (length parts) 2) (second parts) "/"))
         (path (if (find #\? raw-path)
                   (subseq raw-path 0 (position #\? raw-path))
                   raw-path))
         (body (car (last (cl:split-sequence (format nil "~%~%") request-str)))))
    (list method path body)))

#+sbcl
(defun start-tcp-server (port state)
  (let ((socket (make-instance 'sb-bsd-sockets:inet-socket :type :stream :protocol :tcp)))
    (setf (sb-bsd-sockets:sockopt-reuse-address socket) t)
    (sb-bsd-sockets:socket-bind socket (sb-bsd-sockets:make-inet-address "0.0.0.0") port)
    (sb-bsd-sockets:socket-listen socket 5)
    (format t "[id-gen] Listening on port ~a (mode: ~a)~%" port (getf state :mode))
    (format t "[id-gen] SSH identity: ~a~%" (or (getf state :ssh-fp) "none"))
    (setf (getf *server-state* :running) t)
    (loop while (getf *server-state* :running) do
      (let* ((client (sb-bsd-sockets:socket-accept socket))
             (stream (sb-bsd-sockets:socket-make-stream client
                       :input t :output t :buffering :full
                       :element-type 'character)))
        (unwind-protect
          (let* ((req (with-output-to-string (s)
                        (loop for line = (read-line stream nil nil)
                              while (and line (> (length line) 1))
                              do (write-string line s) (write-char #\Newline s))))
                 (parsed (parse-request req))
                 (response (dispatch (second parsed) (first parsed) (third parsed) state)))
            (write-string response stream)
            (finish-output stream))
          (close stream))))))

;;; ─── split-sequence (minimal implementation if not available) ────────────────
(unless (fboundp 'cl:split-sequence)
  (defun cl:split-sequence (delimiter sequence &key (test #'char=))
    (let ((result '()) (current '()))
      (map nil (lambda (c)
                 (if (funcall test c delimiter)
                     (progn (push (coerce (nreverse current) 'string) result)
                            (setf current '()))
                     (push c current)))
           sequence)
      (push (coerce (nreverse current) 'string) result)
      (nreverse result))))

;;; ─── start-server ────────────────────────────────────────────────────────────
(defun start-server (&key (ssh-key nil) (port 7331) (mode :net))
  "Start the id-gen HTTP server.
   :ssh-key  — SSH public key string (establishes identity)
   :port     — TCP port (default 7331)
   :mode     — :net (full API) or :dmz (restricted)"
  (when ssh-key
    (let ((fp (ssh-fingerprint ssh-key)))
      (setf (getf *server-state* :ssh-key) ssh-key)
      (setf (getf *server-state* :ssh-fp)  fp)
      (format t "[id-gen] SSH identity registered: ~a~%" fp)))
  (setf (getf *server-state* :port)       port)
  (setf (getf *server-state* :mode)       mode)
  (setf (getf *server-state* :started-at) (get-universal-time))
  #+sbcl  (start-tcp-server port *server-state*)
  #-sbcl  (format t "[id-gen] Non-SBCL Lisp detected — server stub mode.~%State: ~a~%" *server-state*))

(defun stop-server ()
  (setf (getf *server-state* :running) nil)
  (format t "[id-gen] Server stopped.~%"))

;;; ─── CLI entry point (when run as script) ────────────────────────────────────
(defun main ()
  (let* ((args #+sbcl sb-ext:*posix-argv* #-sbcl '())
         ;; args after "--": ssh-key [port] [mode]
         (rest-args (member "--" args :test #'string=))
         (ssh-key   (when (>= (length rest-args) 2) (second rest-args)))
         (port      (if (>= (length rest-args) 3)
                        (parse-integer (third rest-args) :junk-allowed t) 7331))
         (mode      (if (and (>= (length rest-args) 4)
                             (string= (fourth rest-args) "dmz")) :dmz :net)))
    (format t "~%╔══════════════════════════════════════════════════╗~%")
    (format t "║  id-gen server — Collibra contract ID platform  ║~%")
    (format t "╚══════════════════════════════════════════════════╝~%")
    (format t "  SSH key : ~a~%" (if ssh-key (subseq ssh-key 0 (min 40 (length ssh-key))) "NONE"))
    (format t "  Port    : ~a~%" port)
    (format t "  Mode    : ~a~%" mode)
    (format t "  NS      : c.* (privileged) | a.* (reserved) | b.* (reserved)~%~%")
    (start-server :ssh-key ssh-key :port port :mode mode)))

(main)
