# =============================================================================
# YMRP_04_conversion_gap.R
# Analysis: Does trust differentially moderate sexism vs. racism conversion?
# Tests whether the "sexism advantage" in predicting Trump votes is amplified
# by creator trust. Also tests social media subgroup patterns.
# =============================================================================

source("YMRP_00_setup.R")

# Controls used in all models
CONTROLS <- "faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4"

# =============================================================================
# NOTE ON SCALING
# All attitude predictors (sexism_index, r3, r2) use raw 1-5 Likert scores.
# All three scales run identically from 1 (strongly disagree) to 5 (strongly
# agree), so ORs are directly comparable across attitudes without standardization.
# OR = effect of one Likert unit increase (e.g. neutral → somewhat agree).
# =============================================================================

# =============================================================================
# TEST 1A: Does trust moderate the conversion gap?
# Compare interaction terms across the sexism and racism mobilization models.
# =============================================================================
cat("\n=== TEST 1A: Trust as Moderator — Sexism vs. Racism Conversion ===\n\n")

model_sex_trust <- svyglm(
  as.formula(paste("vote_trump_24 ~ sexism_index * is_truster_binary +", CONTROLS)),
  design = svy, family = quasibinomial()
)

model_r3_trust <- svyglm(
  as.formula(paste("vote_trump_24 ~ r3 * is_truster_binary +", CONTROLS)),
  design = svy, family = quasibinomial()
)

# Extract key coefficients
b_sex_main  <- coef(model_sex_trust)["sexism_index"]
b_sex_int   <- coef(model_sex_trust)["sexism_index:is_truster_binaryTruster"]
b_r3_main   <- coef(model_r3_trust)["r3"]
b_r3_int    <- coef(model_r3_trust)["r3:is_truster_binaryTruster"]

p_sex_int <- summary(model_sex_trust)$coefficients[
  "sexism_index:is_truster_binaryTruster", "Pr(>|t|)"]
p_r3_int  <- summary(model_r3_trust)$coefficients[
  "r3:is_truster_binaryTruster", "Pr(>|t|)"]

cat("Sexism model:\n")
cat("  Main effect (non-trusters):  OR =", round(exp(b_sex_main), 3),
    "| log-odds =", round(b_sex_main, 4), "\n")
cat("  Interaction (trust × score): OR =", round(exp(b_sex_int), 3),
    "| p =", round(p_sex_int, 4), "\n\n")

cat("Racial grievance (r3) model:\n")
cat("  Main effect (non-trusters):  OR =", round(exp(b_r3_main), 3),
    "| log-odds =", round(b_r3_main, 4), "\n")
cat("  Interaction (trust × score): OR =", round(exp(b_r3_int), 3),
    "| p =", round(p_r3_int, 4), "\n\n")

cat("Key comparison:\n")
cat("  Sexism interaction OR:", round(exp(b_sex_int), 3), "\n")
cat("  r3 interaction OR:    ", round(exp(b_r3_int), 3), "\n")
cat("  If both < 1: trust 'flattens' both slopes (creators pull low-scorers in too)\n")
cat("  If sexism interaction OR < r3 interaction OR: trust flattens sexism slope MORE\n")
cat("    → creators uniquely absorb/override sexism as a predictor\n\n")

# =============================================================================
# TEST 1B: Formal three-way test (attitude_type × score × trust)
# Stacked model: does trust differentially moderate sexism vs. racism conversion?
# =============================================================================
cat("=== TEST 1B: Three-Way Stacked Test ===\n")
cat("(Does trust flatten the sexism slope MORE than the racism slope?)\n\n")

dat_3way <- dat |>
  select(weight, faminc5, educ4, race2, pid7_with_leaners, urbancity3, age4,
         sexism_index, r3, is_truster_binary, vote_trump_24) |>
  drop_na() |>
  pivot_longer(
    cols      = c(sexism_index, r3),
    names_to  = "attitude_type",
    values_to = "attitude_score"
  ) |>
  mutate(
    is_sexism  = as.integer(attitude_type == "sexism_index"),
    is_truster = as.integer(is_truster_binary == "Truster")
  )

svy_3way <- svydesign(ids = ~1, weights = ~weight, data = dat_3way)

model_3way <- svyglm(
  vote_trump_24 ~ attitude_score * is_sexism * is_truster +
    faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
  design = svy_3way, family = quasibinomial()
)

summ_3way <- summary(model_3way)

# The three-way interaction: does trust moderate the conversion gap differently
# for sexism vs. racism?
b_3way <- coef(model_3way)["attitude_score:is_sexism:is_truster"]
p_3way <- summ_3way$coefficients["attitude_score:is_sexism:is_truster", "Pr(>|t|)"]

cat("Three-way interaction (attitude_score × is_sexism × is_truster):\n")
cat("  β =", round(b_3way, 4), "| p =", round(p_3way, 4), "\n\n")

if (p_3way < 0.05) {
  cat("  ✓ SIGNIFICANT: Creator trust differentially moderates the sexism vs.\n")
  cat("    racism conversion gap — trust has a distinct effect on the sexism pathway.\n\n")
} else {
  cat("  ✗ Not significant (p =", round(p_3way, 3), ")\n")
  cat("    Trust flattens both slopes similarly — no unique creator effect on sexism.\n\n")
}

# =============================================================================
# TEST 1C: Informal mediation check
# Does the sexism coefficient drop MORE than racism when trust is added?
# If yes: trust is explaining more of the sexism-vote link than the racism-vote link.
# =============================================================================
cat("=== TEST 1C: Mediation-Style Check ===\n")
cat("How much does each attitude coefficient shrink when n_trusted is added?\n\n")

# Without trust
m_sex_no_trust <- svyglm(
  as.formula(paste("vote_trump_24 ~ sexism_index +", CONTROLS)),
  design = svy, family = quasibinomial()
)
m_r3_no_trust <- svyglm(
  as.formula(paste("vote_trump_24 ~ r3 +", CONTROLS)),
  design = svy, family = quasibinomial()
)

# With trust added
m_sex_with_trust <- svyglm(
  as.formula(paste("vote_trump_24 ~ sexism_index + n_trusted +", CONTROLS)),
  design = svy, family = quasibinomial()
)
m_r3_with_trust <- svyglm(
  as.formula(paste("vote_trump_24 ~ r3 + n_trusted +", CONTROLS)),
  design = svy, family = quasibinomial()
)

b_sex_before <- coef(m_sex_no_trust)["sexism_index"]
b_sex_after  <- coef(m_sex_with_trust)["sexism_index"]
b_r3_before  <- coef(m_r3_no_trust)["r3"]
b_r3_after   <- coef(m_r3_with_trust)["r3"]

pct_drop_sex <- (b_sex_before - b_sex_after) / b_sex_before * 100
pct_drop_r3  <- (b_r3_before  - b_r3_after)  / b_r3_before  * 100

cat(sprintf("  Sexism → Trump:  β before = %.4f | β after = %.4f | drop = %.1f%%\n",
            b_sex_before, b_sex_after, pct_drop_sex))
cat(sprintf("  r3 → Trump:      β before = %.4f | β after = %.4f | drop = %.1f%%\n",
            b_r3_before,  b_r3_after,  pct_drop_r3))
cat("\n")

if (pct_drop_sex > pct_drop_r3) {
  cat("  Sexism coefficient drops MORE when trust is added (", round(pct_drop_sex, 1),
      "% vs.", round(pct_drop_r3, 1), "%)\n")
  cat("  → Trust explains more of the sexism-to-vote pathway than the racism-to-vote pathway.\n\n")
} else {
  cat("  r3 coefficient drops more when trust is added — trust is not uniquely\n")
  cat("  mediating the sexism pathway.\n\n")
}

# =============================================================================
# GRAPH 1: Interaction comparison plot
# Side-by-side: predicted Trump probability by attitude score, split by trust,
# for sexism (left) and racial grievance (right).
# Steeper divergence between trust lines = stronger moderation.
# =============================================================================

x_seq        <- seq(1, 5, length.out = 100)
faminc_mean  <- mean(dat$faminc5,    na.rm = TRUE)
educ_mode    <- as.integer(names(sort(table(dat$educ4),             decreasing = TRUE)[1]))
race_mode    <- as.integer(names(sort(table(dat$race2),             decreasing = TRUE)[1]))
pid_mode     <- names(sort(table(dat$pid7_with_leaners), decreasing = TRUE))[1]
urban_mode   <- names(sort(table(dat$urbancity3),        decreasing = TRUE))[1]
age_mode     <- as.integer(names(sort(table(dat$age4),              decreasing = TRUE)[1]))

make_pred_df <- function(model, xvar, att_label) {
  grid <- expand.grid(
    att_score         = x_seq,
    is_truster_binary = c("Non-Truster", "Truster"),
    faminc5           = faminc_mean,
    educ4             = educ_mode,
    race2             = race_mode,
    pid7_with_leaners = pid_mode,
    urbancity3        = urban_mode,
    age4              = age_mode,
    stringsAsFactors  = FALSE
  )
  colnames(grid)[colnames(grid) == "att_score"] <- xvar
  grid$is_truster_binary <- factor(grid$is_truster_binary,
                                   levels = levels(dat$is_truster_binary))
  grid$pid7_with_leaners <- factor(grid$pid7_with_leaners,
                                   levels = levels(dat$pid7_with_leaners))
  grid$urbancity3        <- factor(grid$urbancity3,
                                   levels = levels(dat$urbancity3))
  grid$fit <- plogis(as.numeric(predict(model, newdata = grid, type = "link")))
  grid$x        <- x_seq
  grid$trust    <- grid$is_truster_binary
  grid$attitude <- att_label
  grid[, c("x", "trust", "attitude", "fit")]
}

pred_sex_int <- make_pred_df(model_sex_trust, "sexism_index", "Sexism Index")
pred_r3_int  <- make_pred_df(model_r3_trust,  "r3",           "Racial Grievance (r3)")

plot_int_df <- bind_rows(pred_sex_int, pred_r3_int) |>
  mutate(attitude = factor(attitude, levels = c("Sexism Index", "Racial Grievance (r3)")))

ggplot(plot_int_df, aes(x = x, y = fit, color = trust, linetype = trust)) +
  geom_line(linewidth = 1.1) +
  facet_wrap(~ attitude, labeller = label_value) +
  scale_color_manual(values = c("Non-Truster" = "gray40", "Truster" = "darkred")) +
  scale_x_continuous(
    breaks = 1:5,
    labels = c("1\nStrongly\nDisagree", "2", "3\nNeutral", "4", "5\nStrongly\nAgree"),
    name   = "Attitude Score (raw 1\u20135 Likert)"
  ) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1)) +
  labs(
    title    = "Does Creator Trust Differentially Moderate Attitude Conversion?",
    subtitle = "Predicted Trump vote probability by attitude score and creator trust status",
    y        = "Predicted Probability (Vote Trump)",
    color    = NULL, linetype = NULL,
    caption  =  'Source: YMRP \u00B7 Controls: income, education, race, party ID, urban/rural, age.'
  )

ggsave("figures/04/YMRP_Fig_TrustModerates_Conversion.png",
       width = 9, height = 5.5, dpi = 300)
cat("Saved: figures/04/YMRP_Fig_TrustModerates_Conversion.png\n\n")

# =============================================================================
# TEST 2: Is the sexism conversion advantage concentrated among social media users?
# =============================================================================
cat("\n=== TEST 2: Social Media Habits and the Conversion Gap ===\n\n")

# Helper: run both conversion models in a subgroup and return key ORs
conversion_in_group <- function(data_subset) {
  if (sum(!is.na(data_subset$vote_trump_24)) < 30) {
    return(tibble(att = c("Sexism", "r3"), OR = NA_real_, p = NA_real_, n = nrow(data_subset)))
  }
  svy_sub <- svydesign(ids = ~1, weights = ~weight, data = data_subset)
  m_s <- tryCatch(
    svyglm(as.formula(paste("vote_trump_24 ~ sexism_index +", CONTROLS)),
           design = svy_sub, family = quasibinomial()),
    error = function(e) NULL
  )
  m_r <- tryCatch(
    svyglm(as.formula(paste("vote_trump_24 ~ r3 +", CONTROLS)),
           design = svy_sub, family = quasibinomial()),
    error = function(e) NULL
  )
  tibble(
    att = c("Sexism", "r3"),
    OR  = c(
      if (!is.null(m_s)) exp(coef(m_s)["sexism_index"]) else NA_real_,
      if (!is.null(m_r)) exp(coef(m_r)["r3"])           else NA_real_
    ),
    p = c(
      if (!is.null(m_s)) summary(m_s)$coefficients["sexism_index", "Pr(>|t|)"] else NA_real_,
      if (!is.null(m_r)) summary(m_r)$coefficients["r3",           "Pr(>|t|)"] else NA_real_
    ),
    n = nrow(data_subset)
  )
}

# Subgroups
groups <- list(
  "Alt platform users"       = dat |> filter(alt_platform_user == 1),
  "No alt platforms"         = dat |> filter(alt_platform_user == 0),
  "Right platform users"     = dat |> filter(right_platform_user == 1),
  "No right platforms"       = dat |> filter(right_platform_user == 0),
  "High social media hours"  = dat |> filter(total_social_hrs >= 3),
  "Low social media hours"   = dat |> filter(total_social_hrs <= 1),
  "YouTube users"            = dat |> filter(socialmediause_ymri_21_bin == 1),
  "Non-YouTube users"        = dat |> filter(socialmediause_ymri_21_bin == 0)
)

results_sm <- purrr::map_dfr(groups, conversion_in_group, .id = "group") |>
  mutate(sig = case_when(p < .001 ~ "***", p < .01 ~ "**", p < .05 ~ "*", TRUE ~ ""))

cat("Sexism vs. Racial Grievance ORs by Social Media Subgroup:\n")
cat(sprintf("  %-28s | %-10s %-5s | %-10s %-5s | n\n",
            "Group", "Sex OR", "sig", "r3 OR", "sig"))
cat(strrep("-", 70), "\n")
for (grp in unique(results_sm$group)) {
  row <- results_sm |> filter(group == grp)
  sex_row <- row |> filter(att == "Sexism")
  r3_row  <- row |> filter(att == "r3")
  cat(sprintf("  %-28s | OR = %-5s %-3s | OR = %-5s %-3s | %d\n",
              grp,
              round(sex_row$OR, 2), sex_row$sig,
              round(r3_row$OR,  2), r3_row$sig,
              sex_row$n))
}
cat("\n")

# =============================================================================
# GRAPH 2: Dot-and-CI chart comparing sexism vs. r3 ORs across subgroups
# =============================================================================

# Re-run with CIs for plotting
conversion_with_ci <- function(data_subset, group_label) {
  if (sum(!is.na(data_subset$vote_trump_24)) < 30) return(NULL)
  svy_sub <- svydesign(ids = ~1, weights = ~weight, data = data_subset)
  
  get_ci <- function(model, coef_name) {
    ci <- tryCatch(confint(model)[coef_name, ], error = function(e) c(NA, NA))
    tibble(
      OR  = exp(coef(model)[coef_name]),
      lo  = exp(ci[1]),
      hi  = exp(ci[2])
    )
  }
  
  m_s <- tryCatch(
    svyglm(as.formula(paste("vote_trump_24 ~ sexism_index +", CONTROLS)),
           design = svy_sub, family = quasibinomial()), error = function(e) NULL)
  m_r <- tryCatch(
    svyglm(as.formula(paste("vote_trump_24 ~ r3 +", CONTROLS)),
           design = svy_sub, family = quasibinomial()), error = function(e) NULL)
  
  bind_rows(
    if (!is.null(m_s)) get_ci(m_s, "sexism_index") |> mutate(att = "Sexism Index"),
    if (!is.null(m_r)) get_ci(m_r, "r3")           |> mutate(att = "Racial Grievance (r3)")
  ) |> mutate(group = group_label)
}

ci_results <- purrr::map2_dfr(
  groups, names(groups), conversion_with_ci
) |>
  mutate(
    att   = factor(att, levels = c("Sexism Index", "Racial Grievance (r3)")),
    group = factor(group, levels = rev(names(groups)))
  )

ggplot(ci_results, aes(x = OR, y = group, color = att, shape = att)) +
  geom_vline(xintercept = 1, linetype = "dashed", color = "gray60") +
  geom_errorbar(aes(xmin = lo, xmax = hi),
                orientation = "y",
                width = 0.2, position = position_dodge(0.5)) +
  geom_point(size = 3, position = position_dodge(0.5)) +
  scale_color_manual(values = c("Sexism Index"           = "darkred",
                                "Racial Grievance (r3)"  = "darkorange")) +
  scale_shape_manual(values = c("Sexism Index" = 16, "Racial Grievance (r3)" = 17)) +
  scale_x_continuous(
    trans  = "log",
    breaks = c(0.5, 1, 1.5, 2, 3, 4, 6),
    labels = c("0.5", "1.0", "1.5", "2.0", "3.0", "4.0", "6.0")
  ) +
  labs(
    title    = "Sexism vs. Racial Grievance Conversion Across Social Media Subgroups",
    subtitle = "Odds ratio: each attitude\u2019s association with Trump vote (standardized 0\u20131)",
    x        = "Odds Ratio (log scale) | OR > 1 = attitude predicts Trump vote",
    y        = NULL,
    color    = NULL, shape = NULL,
    caption  = "Source: YMRP \u00B7 Controls: income, education, race, party ID, urban/rural, age."
  ) +
  theme(axis.text.y = element_text(size = 13))

ggsave("figures/04/YMRP_Fig_SocialMedia_ConversionGap.png",
       width = 9, height = 6.5, dpi = 300)
cat("Saved: figures/04/YMRP_Fig_SocialMedia_ConversionGap.png\n\n")

# =============================================================================
# EXPORT: Summary tables to CSV
# =============================================================================

tbl_sex_trust <- tbl_regression(
  model_sex_trust, exponentiate = TRUE,
  label = list(
    sexism_index                                      ~ "Sexism Index (1-5)",
    is_truster_binary                                 ~ "Trusts Creators (Binary)",
    `sexism_index:is_truster_binary`                  ~ "Interaction: Sexism \u00d7 Trusts Creators",
    faminc5                                           ~ "Family Income (Quintile)",
    educ4                                             ~ "Education (4-Level)",
    race2                                             ~ "Race (Binary)",
    pid7_with_leaners                                 ~ "Party ID (3-cat)",
    urbancity3                                        ~ "Urban/Rural (3-cat)",
    age4                                              ~ "Age Group"
  )
) |> bold_labels() |> bold_p(t = 0.05)

tbl_r3_trust <- tbl_regression(
  model_r3_trust, exponentiate = TRUE,
  label = list(
    r3                                    ~ "Racial Grievance / r3 (1-5)",
    is_truster_binary                     ~ "Trusts Creators (Binary)",
    `r3:is_truster_binary`                ~ "Interaction: r3 \u00d7 Trusts Creators",
    faminc5                               ~ "Family Income (Quintile)",
    educ4                                 ~ "Education (4-Level)",
    race2                                 ~ "Race (Binary)",
    pid7_with_leaners                     ~ "Party ID (3-cat)",
    urbancity3                            ~ "Urban/Rural (3-cat)",
    age4                                  ~ "Age Group"
  )
) |> bold_labels() |> bold_p(t = 0.05)

write_csv(as_tibble(tbl_sex_trust), "tables/04/YMRP_ModelA_Sexism_TrustModeration.csv")
write_csv(as_tibble(tbl_r3_trust),  "tables/04/YMRP_ModelB_r3_TrustModeration.csv")

cat("Exported: tables/04/ — 2 model CSVs\n")
cat("\n=== File 04 Complete ===\n")