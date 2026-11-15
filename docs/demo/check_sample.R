# Numerical check of the sample theorem (worked example 5), in R.
# Evidence only: it cannot prove or refute anything, and cannot raise a status.
#
# Claim checked: "if f is differentiable and f'(x0) = 0, then f has a global minimum at x0".
#   1. f(x) = -x^2 at x0 = 0: finite differences give f'(0) = 0, yet f(1) < f(0).
#      This is reported under "violations" as a counterexample candidate to the claim.
#   2. The repair (Theorem 2): for random convex f with f'(x0) = 0, check f(x0) <= f(y)
#      at random y. Any failure would be a violation of the repair.
#
# Run by the runner: reads MP_SEED, MP_PARAMS {"n": instances, "m": points per instance},
# writes one JSON object to MP_OUT.

seed <- as.integer(Sys.getenv("MP_SEED", "1"))
params <- jsonlite::fromJSON(Sys.getenv("MP_PARAMS", "{}"))
n <- if (is.null(params$n)) 1000L else as.integer(params$n)
m <- if (is.null(params$m)) 200L else as.integer(params$m)
set.seed(seed)

# 1. The counterexample f(x) = -x^2.
f <- function(x) -x^2
h <- 10^-(1:6)
fd <- (f(h) - f(-h)) / (2 * h)            # central differences at 0
grid <- seq(-10, 10, by = 0.01)
cex <- list(
  max_abs_central_difference = max(abs(fd)),
  f_at_1 = f(1), f_at_0 = f(0),
  f0_is_grid_maximum = isTRUE(all.equal(max(f(grid)), f(0)))
)
violations <- list()
if (cex$max_abs_central_difference < 1e-12 && f(1) < f(0)) {
  violations[[1]] <- list(f = "-x^2", x0 = 0, y = 1, f_x0 = f(0), f_y = f(1),
                          note = "f'(x0) = 0 but f(y) < f(x0)")
}

# 2. The repair: f(x) = sum_i a_i (x - c_i)^2 + b * log(1 + exp(x - d)), convex for a_i, b > 0.
worst <- Inf
repair_failures <- 0L
for (k in seq_len(n)) {
  a <- runif(3, 0.1, 2); cc <- rnorm(3, 0, 3); b <- runif(1, 0, 3); d <- rnorm(1, 0, 3)
  g <- function(x) sum(a * (x - cc)^2) + b * log1p(exp(x - d))
  dg <- function(x) sum(2 * a * (x - cc)) + b * plogis(x - d)
  x0 <- uniroot(dg, c(-100, 100), tol = 1e-12)$root   # dg is increasing, so one root
  ys <- rnorm(m, x0, 5)
  gap <- min(vapply(ys, g, numeric(1)) - g(x0))      # should be >= 0
  worst <- min(worst, gap)
  if (gap < -1e-9) repair_failures <- repair_failures + 1L
}

out <- list(
  seed = seed, n = n, m = m,
  counterexample = cex,
  repair = list(instances = n, points_each = m, failures = repair_failures,
                min_gap_f_y_minus_f_x0 = worst),
  violations = violations
)
jsonlite::write_json(out, Sys.getenv("MP_OUT", "out.json"), auto_unbox = TRUE, digits = NA)
