package io.sindoc.collibra.edge;

import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Objects;

/**
 * Contract for the Collibra Edge Site installer lifecycle.
 *
 * <p>{@code EdgeSiteInstaller} governs the end-to-end deployment of the real Collibra
 * Edge onto a Kubernetes cluster using the site-specific TGZ installer bundle distributed
 * by Collibra.  The TGZ contains:
 * <ul>
 *   <li>{@code collibra-edge-helm-chart/} — the vendored Helm chart</li>
 *   <li>{@code site-values.yaml} — site-scoped overrides (siteId, platformId,
 *       installerVersion)</li>
 *   <li>{@code registries.yaml} — Docker registry credentials for
 *       {@code edge-docker-delivery.repository.collibra.io}</li>
 *   <li>{@code properties.yaml} — additional installer properties</li>
 * </ul>
 *
 * <h2>Deployment targets</h2>
 * <ul>
 *   <li>Bundled k3s — RHEL 8.8+ bare-metal or VM
 *       ({@link DeploymentMode#K3S})</li>
 *   <li>Managed Kubernetes — EKS, GKE, AKS
 *       ({@link DeploymentMode#HELM_MANAGED_K8S})</li>
 *   <li>OpenShift — OCP 4.x
 *       ({@link DeploymentMode#HELM_OPENSHIFT})</li>
 * </ul>
 *
 * <h2>Installation steps</h2>
 * <ol>
 *   <li>Verify prerequisites ({@link #checkPrerequisites()}).</li>
 *   <li>Create Kubernetes namespace {@code collibra-edge} if absent.</li>
 *   <li>Create image-pull secrets from {@code registries.yaml}.</li>
 *   <li>Apply {@code edge-secret.yaml} for licence and platform tokens.</li>
 *   <li>Execute {@code helm install} (first install) or {@code helm upgrade}
 *       (subsequent call) using {@code collibra-edge-helm-chart/} and
 *       {@code site-values.yaml}.</li>
 *   <li>Wait for all pods to reach {@code Ready} state; report result via
 *       {@link InstallerResult}.</li>
 * </ol>
 *
 * <p>After a successful install, Collibra DGC cloud marks the site as
 * <em>Installed</em> once the edge pods call home to
 * {@code https://lutino.collibra.com/}.
 *
 * <h2>Site-specific coordinates</h2>
 * <pre>
 *   siteId            = 6569521c-dad2-45a2-aed7-ca2008bc571a
 *   platformId        = https://lutino.collibra.com/
 *   installerVersion  = 2026.3.7-8
 * </pre>
 *
 * @since 2026.3
 * @see CollibraEdgeSiteApi
 * @see EdgeSiteException
 */
public interface EdgeSiteInstaller {

    // ── Nested types ──────────────────────────────────────────────────────────

    /**
     * Deployment mode that determines which Kubernetes distribution and Helm
     * invocation style the installer uses.
     *
     * @since 2026.3
     * @see CollibraEdgeSiteApi
     */
    enum DeploymentMode {

        /**
         * Bundled k3s distribution managed by the Collibra installer script.
         *
         * <p>Requires a Linux host running RHEL 8.8 or later.  The installer
         * provisions k3s automatically before applying the Helm chart.
         */
        K3S {
            @Override
            public boolean requiresLinux() {
                return true;
            }

            @Override
            public String description() {
                return "Bundled k3s on RHEL 8.8+ (installer-managed Kubernetes)";
            }
        },

        /**
         * Externally managed Kubernetes cluster (EKS, GKE, AKS, or any
         * CNCF-conformant distribution).
         *
         * <p>The installer assumes a functioning cluster is reachable via the
         * active {@code kubectl} context.  No Linux requirement is imposed on the
         * workstation running the installer.
         */
        HELM_MANAGED_K8S {
            @Override
            public boolean requiresLinux() {
                return false;
            }

            @Override
            public String description() {
                return "Helm install on managed Kubernetes (EKS / GKE / AKS)";
            }
        },

        /**
         * Red Hat OpenShift Container Platform 4.x.
         *
         * <p>Uses the same Helm chart as {@link #HELM_MANAGED_K8S} but applies
         * OpenShift-specific security context constraints (SCCs) and route
         * objects.  Does not require the workstation to run Linux.
         */
        HELM_OPENSHIFT {
            @Override
            public boolean requiresLinux() {
                return false;
            }

            @Override
            public String description() {
                return "Helm install on Red Hat OpenShift Container Platform 4.x";
            }
        };

        /**
         * Returns {@code true} if this deployment mode requires the installer to
         * run on a Linux host.
         *
         * <p>{@link #K3S} is the only mode that mandates Linux because it
         * bootstraps k3s directly on the host OS.
         *
         * @return {@code true} when a Linux operating system is required
         */
        public abstract boolean requiresLinux();

        /**
         * Returns a human-readable description of this deployment mode suitable
         * for log output and governance records.
         *
         * @return a non-null, non-empty description string
         */
        public abstract String description();
    }

    // ── Value types ───────────────────────────────────────────────────────────

    /**
     * Snapshot of a single Kubernetes pod's status as reported by
     * {@code kubectl get pods}.
     *
     * <p>Instances are created by {@link InstallerStatus} and returned from
     * {@link EdgeSiteInstaller#status(String)}.
     *
     * @since 2026.3
     * @see InstallerStatus
     */
    final class PodStatus {

        /** The pod name as returned by {@code kubectl get pods}. */
        private final String name;

        /**
         * Container readiness in {@code "ready/total"} format, e.g. {@code "2/2"}.
         */
        private final String ready;

        /**
         * Pod phase or condensed status string, e.g. {@code "Running"},
         * {@code "CrashLoopBackOff"}.
         */
        private final String status;

        /** Total number of container restarts across all containers in the pod. */
        private final int restarts;

        /**
         * Human-readable pod age as reported by kubectl, e.g. {@code "5m"},
         * {@code "2h"}, {@code "3d"}.
         */
        private final String age;

        /**
         * Constructs a {@code PodStatus} snapshot.
         *
         * @param name     the pod name; must not be {@code null}
         * @param ready    readiness string in {@code "ready/total"} format;
         *                 must not be {@code null}
         * @param status   pod phase or condensed status string; must not be
         *                 {@code null}
         * @param restarts total container restart count; must be non-negative
         * @param age      human-readable pod age as reported by kubectl;
         *                 must not be {@code null}
         */
        public PodStatus(String name, String ready, String status,
                         int restarts, String age) {
            this.name     = Objects.requireNonNull(name,   "name");
            this.ready    = Objects.requireNonNull(ready,  "ready");
            this.status   = Objects.requireNonNull(status, "status");
            this.restarts = restarts;
            this.age      = Objects.requireNonNull(age,    "age");
        }

        /**
         * Returns the pod name.
         *
         * @return non-null pod name
         */
        public String getName() { return name; }

        /**
         * Returns the readiness string in {@code "ready/total"} format.
         *
         * @return non-null readiness string, e.g. {@code "2/2"}
         */
        public String getReady() { return ready; }

        /**
         * Returns the pod phase or condensed status string.
         *
         * @return non-null status string, e.g. {@code "Running"}
         */
        public String getStatus() { return status; }

        /**
         * Returns the total container restart count across all containers.
         *
         * @return non-negative restart count
         */
        public int getRestarts() { return restarts; }

        /**
         * Returns the human-readable pod age as reported by kubectl.
         *
         * @return non-null age string, e.g. {@code "5m"}
         */
        public String getAge() { return age; }

        @Override
        public String toString() {
            return "PodStatus{name='" + name + "', ready='" + ready
                    + "', status='" + status + "', restarts=" + restarts
                    + ", age='" + age + "'}";
        }
    }

    /**
     * Full installer status snapshot for a given Kubernetes namespace, combining
     * Helm release metadata and live pod state.
     *
     * <p>Returned by {@link EdgeSiteInstaller#status(String)}.
     *
     * @since 2026.3
     * @see EdgeSiteInstaller#status(String)
     * @see CollibraEdgeSiteApi
     */
    final class InstallerStatus {

        /** Kubernetes namespace inspected, e.g. {@code "collibra-edge"}. */
        private final String namespace;

        /**
         * Active {@code kubectl} context name at the time the status was sampled.
         */
        private final String context;

        /**
         * Helm release name, e.g. {@code "collibra-edge"}.  {@code null} if no
         * Helm release is present in the namespace.
         */
        private final String helmRelease;

        /**
         * Human-readable Helm release name used in the {@code helm install}
         * command.
         */
        private final String releaseName;

        /**
         * Installed chart version, e.g. {@code "2026.3.7-8"}.  {@code null} if
         * no Helm release is present.
         */
        private final String releaseVersion;

        /** Live pod status entries from {@code kubectl get pods -n namespace}. */
        private final List<PodStatus> pods;

        /**
         * {@code true} if all pods report all containers ready (readiness string
         * numerator equals denominator and status is {@code Running}).
         */
        private final boolean healthy;

        /** Instant at which this snapshot was taken. */
        private final Instant reportedAt;

        /**
         * Constructs an {@code InstallerStatus} snapshot.
         *
         * @param namespace      Kubernetes namespace; must not be {@code null}
         * @param context        active kubectl context name; must not be
         *                       {@code null}
         * @param helmRelease    Helm release identifier, or {@code null} if absent
         * @param releaseName    human-readable Helm release name; must not be
         *                       {@code null}
         * @param releaseVersion installed chart version, or {@code null} if absent
         * @param pods           live pod status list; must not be {@code null}
         * @param healthy        {@code true} when all pods are fully ready
         * @param reportedAt     sampling instant; must not be {@code null}
         */
        public InstallerStatus(String namespace, String context,
                               String helmRelease, String releaseName,
                               String releaseVersion, List<PodStatus> pods,
                               boolean healthy, Instant reportedAt) {
            this.namespace      = Objects.requireNonNull(namespace,   "namespace");
            this.context        = Objects.requireNonNull(context,     "context");
            this.helmRelease    = helmRelease;
            this.releaseName    = Objects.requireNonNull(releaseName, "releaseName");
            this.releaseVersion = releaseVersion;
            this.pods           = Objects.requireNonNull(pods,        "pods");
            this.healthy        = healthy;
            this.reportedAt     = Objects.requireNonNull(reportedAt,  "reportedAt");
        }

        /**
         * Returns the Kubernetes namespace that was inspected.
         *
         * @return non-null namespace string
         */
        public String getNamespace() { return namespace; }

        /**
         * Returns the active kubectl context name at sampling time.
         *
         * @return non-null context name
         */
        public String getContext() { return context; }

        /**
         * Returns the Helm release identifier, or {@code null} if no Helm
         * release is present in the namespace.
         *
         * @return Helm release identifier, possibly {@code null}
         */
        public String getHelmRelease() { return helmRelease; }

        /**
         * Returns the human-readable Helm release name used in the
         * {@code helm install} command.
         *
         * @return non-null release name
         */
        public String getReleaseName() { return releaseName; }

        /**
         * Returns the installed chart version, or {@code null} if no Helm
         * release is present.
         *
         * @return chart version string, possibly {@code null}
         */
        public String getReleaseVersion() { return releaseVersion; }

        /**
         * Returns the live pod status entries for the namespace.
         *
         * @return non-null, possibly empty, immutable list of pod statuses
         */
        public List<PodStatus> getPods() { return pods; }

        /**
         * Returns {@code true} if all pods are fully ready.
         *
         * @return {@code true} when every pod reports all containers ready and
         *         is in {@code Running} state
         */
        public boolean isHealthy() { return healthy; }

        /**
         * Returns the instant at which this snapshot was sampled.
         *
         * @return non-null sampling instant
         */
        public Instant getReportedAt() { return reportedAt; }

        @Override
        public String toString() {
            return "InstallerStatus{namespace='" + namespace + "', helmRelease='"
                    + helmRelease + "', releaseVersion='" + releaseVersion
                    + "', pods=" + pods.size() + ", healthy=" + healthy
                    + ", reportedAt=" + reportedAt + '}';
        }
    }

    /**
     * Result of an {@link EdgeSiteInstaller#install(Path, DeploymentMode)} or
     * {@link EdgeSiteInstaller#uninstall(String)} operation.
     *
     * <p>A result with {@link #isOk()} {@code = false} always carries a non-null,
     * non-empty {@link #getErrorMessage()}.
     *
     * @since 2026.3
     * @see EdgeSiteInstaller#install(Path, DeploymentMode)
     * @see EdgeSiteInstaller#uninstall(String)
     * @see CollibraEdgeSiteApi
     */
    final class InstallerResult {

        /** {@code true} if the operation completed without error. */
        private final boolean ok;

        /**
         * Deployment mode in effect during the operation.  May be {@code null}
         * for {@code uninstall} results.
         */
        private final DeploymentMode mode;

        /** Kubernetes namespace targeted by the operation. */
        private final String namespace;

        /**
         * Chart version installed or upgraded to.  {@code null} for
         * {@code uninstall} results or when the operation failed before the
         * Helm step.
         */
        private final String releaseVersion;

        /** Wall-clock duration of the operation in milliseconds. */
        private final long durationMs;

        /**
         * Human-readable error description when {@link #isOk()} is {@code false};
         * {@code null} on success.
         */
        private final String errorMessage;

        /**
         * Constructs an {@code InstallerResult}.
         *
         * @param ok             {@code true} if the operation succeeded
         * @param mode           deployment mode, or {@code null} for uninstall
         *                       results
         * @param namespace      Kubernetes namespace targeted; must not be
         *                       {@code null}
         * @param releaseVersion chart version installed, or {@code null} if not
         *                       applicable
         * @param durationMs     wall-clock operation duration in milliseconds;
         *                       must be non-negative
         * @param errorMessage   error description when {@code ok = false};
         *                       {@code null} on success
         */
        public InstallerResult(boolean ok, DeploymentMode mode, String namespace,
                               String releaseVersion, long durationMs,
                               String errorMessage) {
            this.ok             = ok;
            this.mode           = mode;
            this.namespace      = Objects.requireNonNull(namespace, "namespace");
            this.releaseVersion = releaseVersion;
            this.durationMs     = durationMs;
            this.errorMessage   = errorMessage;
        }

        /**
         * Returns {@code true} if the install or uninstall operation completed
         * without error.
         *
         * @return {@code true} on success
         */
        public boolean isOk() { return ok; }

        /**
         * Returns the deployment mode that was in effect, or {@code null} for
         * uninstall results.
         *
         * @return deployment mode, possibly {@code null}
         */
        public DeploymentMode getMode() { return mode; }

        /**
         * Returns the Kubernetes namespace targeted by the operation.
         *
         * @return non-null namespace string
         */
        public String getNamespace() { return namespace; }

        /**
         * Returns the chart version installed or upgraded to, or {@code null}
         * when not applicable (uninstall, or failure before Helm step).
         *
         * @return chart version string, possibly {@code null}
         */
        public String getReleaseVersion() { return releaseVersion; }

        /**
         * Returns the wall-clock duration of the operation in milliseconds.
         *
         * @return non-negative duration in milliseconds
         */
        public long getDurationMs() { return durationMs; }

        /**
         * Returns the error message when {@link #isOk()} is {@code false}, or
         * {@code null} on success.
         *
         * @return error description, or {@code null} if the operation succeeded
         */
        public String getErrorMessage() { return errorMessage; }

        @Override
        public String toString() {
            return "InstallerResult{ok=" + ok + ", mode=" + mode
                    + ", namespace='" + namespace + "', releaseVersion='"
                    + releaseVersion + "', durationMs=" + durationMs
                    + (ok ? "" : ", errorMessage='" + errorMessage + "'") + '}';
        }
    }

    // ── Interface methods ─────────────────────────────────────────────────────

    /**
     * Runs the full install or upgrade of the Collibra Edge onto the target
     * Kubernetes cluster.
     *
     * <p>Equivalent to calling
     * {@link #install(Path, DeploymentMode, boolean) install(installerDir, mode, false)}.
     *
     * <p>The method:
     * <ol>
     *   <li>Calls {@link #checkPrerequisites()} and aborts with a failed
     *       {@link InstallerResult} if any prerequisite is missing.</li>
     *   <li>Creates namespace {@code collibra-edge} if absent.</li>
     *   <li>Creates image-pull secrets from {@code registries.yaml} inside
     *       {@code installerDir}.</li>
     *   <li>Applies {@code edge-secret.yaml} for platform tokens.</li>
     *   <li>Executes {@code helm install} (first run) or {@code helm upgrade}
     *       (subsequent run) using the chart and {@code site-values.yaml} in
     *       {@code installerDir}.</li>
     *   <li>Waits for pods to reach {@code Ready} using a default timeout.</li>
     * </ol>
     *
     * @param installerDir path to the extracted TGZ directory containing
     *                     {@code collibra-edge-helm-chart/},
     *                     {@code site-values.yaml}, {@code registries.yaml},
     *                     and {@code properties.yaml}; must not be {@code null}
     * @param mode         the deployment target mode; must not be {@code null}
     * @return a non-null {@link InstallerResult} describing the outcome;
     *         {@link InstallerResult#isOk()} is {@code true} on success
     * @throws EdgeSiteException if an unrecoverable error occurs during the
     *                           Helm or Kubernetes operations, or if
     *                           prerequisite verification itself throws
     * @since 2026.3
     * @see #install(Path, DeploymentMode, boolean)
     * @see CollibraEdgeSiteApi
     */
    InstallerResult install(Path installerDir, DeploymentMode mode)
            throws EdgeSiteException;

    /**
     * Runs the install or upgrade with optional dry-run support.
     *
     * <p>When {@code dryRun} is {@code true} the method passes {@code --dry-run}
     * to the underlying {@code helm install} / {@code helm upgrade} command and
     * returns a result whose {@link InstallerResult#isOk()} reflects whether the
     * Helm template rendering and manifest validation succeeded, without touching
     * the cluster.
     *
     * <p>When {@code dryRun} is {@code false} this method behaves identically to
     * {@link #install(Path, DeploymentMode)}.
     *
     * @param installerDir path to the extracted TGZ directory; must not be
     *                     {@code null}
     * @param mode         the deployment target mode; must not be {@code null}
     * @param dryRun       when {@code true}, passes {@code --dry-run} to Helm and
     *                     does not modify cluster state
     * @return a non-null {@link InstallerResult} describing the outcome (or
     *         the dry-run validation result)
     * @throws EdgeSiteException if an unrecoverable error occurs during the
     *                           Helm or Kubernetes operations
     * @since 2026.3
     * @see #install(Path, DeploymentMode)
     * @see CollibraEdgeSiteApi
     */
    InstallerResult install(Path installerDir, DeploymentMode mode, boolean dryRun)
            throws EdgeSiteException;

    /**
     * Uninstalls the Collibra Edge Helm release and deletes the Kubernetes
     * namespace.
     *
     * <p>Executes the following steps:
     * <ol>
     *   <li>{@code helm uninstall <release> -n <namespace>}</li>
     *   <li>{@code kubectl delete namespace <namespace>}</li>
     * </ol>
     *
     * <p>If the namespace or Helm release does not exist, the method returns a
     * successful {@link InstallerResult} without error (idempotent).
     *
     * @param namespace the Kubernetes namespace to remove; must not be
     *                  {@code null} or blank; typically {@code "collibra-edge"}
     * @return a non-null {@link InstallerResult};
     *         {@link InstallerResult#isOk()} is {@code true} on success
     * @throws EdgeSiteException if the helm or kubectl command fails with an
     *                           unexpected exit code or the cluster is
     *                           unreachable
     * @since 2026.3
     * @see CollibraEdgeSiteApi
     */
    InstallerResult uninstall(String namespace) throws EdgeSiteException;

    /**
     * Returns a live status snapshot for the given Kubernetes namespace.
     *
     * <p>Combines the output of {@code kubectl get pods -n namespace} and
     * {@code helm status <release> -n namespace} into a single
     * {@link InstallerStatus}.
     *
     * @param namespace the Kubernetes namespace to inspect; must not be
     *                  {@code null} or blank; typically {@code "collibra-edge"}
     * @return a non-null {@link InstallerStatus} snapshot;
     *         {@link InstallerStatus#isHealthy()} is {@code true} only when all
     *         pods are fully ready
     * @throws EdgeSiteException if the kubectl or helm commands cannot be
     *                           executed, or the cluster is unreachable
     * @since 2026.3
     * @see CollibraEdgeSiteApi
     */
    InstallerStatus status(String namespace) throws EdgeSiteException;

    /**
     * Verifies that all required tools are on the system {@code PATH} and that
     * the Kubernetes cluster is reachable via the active {@code kubectl} context.
     *
     * <p>Checked tools:
     * <ul>
     *   <li>{@code helm} — Helm 3.x</li>
     *   <li>{@code kubectl} — any recent version compatible with the target
     *       cluster</li>
     *   <li>{@code jq} — used by installer helper scripts</li>
     *   <li>{@code yq} — used for YAML merging and site-values patching</li>
     * </ul>
     *
     * <p>Cluster reachability is verified by running
     * {@code kubectl cluster-info} and checking for a non-error exit code.
     *
     * @return {@code true} if every required tool is found on {@code PATH} and
     *         the Kubernetes API server responds; {@code false} if any check
     *         fails (detailed failure reasons are written to the implementation's
     *         logger)
     * @since 2026.3
     * @see CollibraEdgeSiteApi
     */
    boolean checkPrerequisites();

    /**
     * Blocks until all pods in the given namespace are {@code Ready}, or until
     * the specified timeout elapses.
     *
     * <p>Polls {@code kubectl get pods -n namespace} at a regular interval.
     * A pod is considered ready when the readiness numerator equals the
     * denominator (e.g. {@code "2/2"}) and the status is {@code Running}.
     *
     * <p>The method returns normally only when every pod is ready.  If the
     * timeout elapses before all pods are ready it throws
     * {@link EdgeSiteException} with code
     * {@link EdgeSiteException.Code#INVALID_STATE}.
     *
     * @param namespace the Kubernetes namespace to watch; must not be
     *                  {@code null} or blank; typically {@code "collibra-edge"}
     * @param timeout   the maximum duration to wait; must not be {@code null}
     *                  or negative
     * @throws EdgeSiteException if the timeout elapses before all pods reach
     *                           {@code Ready}, or if the cluster becomes
     *                           unreachable during the wait, with code
     *                           {@link EdgeSiteException.Code#INVALID_STATE} or
     *                           {@link EdgeSiteException.Code#INTERNAL_ERROR}
     *                           respectively
     * @since 2026.3
     * @see #status(String)
     * @see CollibraEdgeSiteApi
     */
    void waitForHealthy(String namespace, Duration timeout) throws EdgeSiteException;
}
