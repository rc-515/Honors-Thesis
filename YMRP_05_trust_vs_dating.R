# =============================================================================
# YMRP_05_trust_vs_dating.R
# Models: Does romantic history / loneliness predict manosphere involvement?
#   Model A: Binary logistic (is_true_believer)
#   Model B: Ordered logistic (fan_status: Non-Fan / Skeptical / True Believer)
#   Model C: Linear dosage (n_trusted)
#   Model D: Stress test — controlling for party ID
# Uses survey weights via svyglm() / svyolr(). Exports tables to Word.
# =============================================================================

source("YMRP_00_setup.R")
# NOTE: svyolr() handles weighted ordered logistic regression.
# For the binary and linear models we use svyglm() as in other files.

CONTROLS <- "faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4"

# =============================================================================
# MODEL A: BINARY LOGISTIC
# DV: is_true_believer (1 = trusts at least one creator at highest level)
# =============================================================================
cat("\n=== MODEL A: Binary Logistic — Predictors of True Believer Status ===\n")

model_A <- svyglm(
  as.formula(paste(
    "is_true_believer ~ loneliness + never_relationship + recent_breakup +",
    CONTROLS
  )),
  design = svy,
  family = quasibinomial()
)

summary(model_A)
cat("\n--- Odds Ratios ---\n")
print(round(exp(coef(model_A)), 3))

# =============================================================================
# MODEL B: ORDERED LOGISTIC
# DV: fan_status (Non-Fan / Skeptical Fan / True Believer)
# svyolr() is the survey-weighted equivalent of polr()
# =============================================================================
cat("\n=== MODEL B: Ordered Logistic — Predicting Fan Hierarchy Level ===\n")

model_B <- svyolr(
  as.formula(paste(
    "fan_status ~ loneliness + never_relationship + recent_breakup +",
    CONTROLS
  )),
  design = svy
)

summary(model_B)

# p-values for ordered logit (t-based approximation)
ctable        <- coef(summary(model_B))
p_vals        <- pnorm(abs(ctable[, "t value"]), lower.tail = FALSE) * 2
ctable_with_p <- cbind(ctable, "p value" = round(p_vals, 4))
cat("\n--- Coefficients with p-values ---\n")
print(ctable_with_p)
cat("\n--- Odds Ratios (Ordered Logit) ---\n")
print(round(exp(coef(model_B)), 3))

# =============================================================================
# MODEL C: OLS DOSAGE
# DV: n_trusted (continuous count, 0-11)
# =============================================================================
cat("\n=== MODEL C: OLS Dosage — Predicting Number of Creators Trusted ===\n")

model_C <- svyglm(
  as.formula(paste(
    "n_trusted ~ loneliness + never_relationship + recent_breakup +",
    CONTROLS
  )),
  design = svy,
  family = gaussian()
)

summary(model_C)

# =============================================================================
# KEY FINDINGS SUMMARY
# =============================================================================
cat("\n--- Key Findings Summary ---\n")

or_breakup_A <- exp(coef(model_A)["recent_breakup"])
or_never_A   <- exp(coef(model_A)["never_relationship"])
or_lonely_A  <- exp(coef(model_A)["loneliness"])
dosage_breakup <- coef(model_C)["recent_breakup"]
dosage_lonely  <- coef(model_C)["loneliness"]
dosage_never   <- coef(model_C)["never_relationship"]

cat(sprintf("Model A — Recent breakup OR:         %.2f (%+.0f%% vs. no recent breakup)\n",
            or_breakup_A, (or_breakup_A - 1) * 100))
cat(sprintf("Model A — Never in relationship OR:  %.2f (%+.0f%% vs. has been in one)\n",
            or_never_A, (or_never_A - 1) * 100))
cat(sprintf("Model A — Loneliness OR (per unit):  %.2f (%+.0f%% per 1-pt Likert increase)\n",
            or_lonely_A, (or_lonely_A - 1) * 100))
cat(sprintf("Model C — Breakup dosage effect:     %+.2f creators trusted\n", dosage_breakup))
cat(sprintf("Model C — Loneliness dosage effect:  %+.2f creators per 1-pt Likert increase\n", dosage_lonely))
cat(sprintf("Model C — Never relationship effect: %+.2f creators trusted\n", dosage_never))

# =============================================================================
# EXPORT: Regression Tables to Word
# =============================================================================

tbl_A <- tbl_regression(
  model_A,
  exponentiate = TRUE,
  label = list(
    loneliness         ~ "Loneliness (1-5 Likert)",
    never_relationship ~ "Never Been in Serious Relationship",
    recent_breakup     ~ "Recent Breakup (Within 12 Months)",
    faminc5            ~ "Family Income (Quintile)",
    educ4              ~ "Education (4-Level)",
    race2              ~ "Race (Binary)",
    pid7_with_leaners  ~ "Party ID (3-cat)",
    urbancity3         ~ "Urban/Rural (3-cat)",
    age4               ~ "Age Group"
  )
) |>
  bold_labels() |> bold_p(t = 0.05) |>
  modify_caption("**Model A: Binary Logistic — Predictors of True Believer Status (Weighted)**")

tbl_C <- tbl_regression(
  model_C,
  label = list(
    loneliness         ~ "Loneliness (1-5 Likert)",
    never_relationship ~ "Never Been in Serious Relationship",
    recent_breakup     ~ "Recent Breakup (Within 12 Months)",
    faminc5            ~ "Family Income (Quintile)",
    educ4              ~ "Education (4-Level)",
    race2              ~ "Race (Binary)",
    pid7_with_leaners  ~ "Party ID (3-cat)",
    urbancity3         ~ "Urban/Rural (3-cat)",
    age4               ~ "Age Group"
  )
) |>
  bold_labels() |> bold_p(t = 0.05) |>
  modify_caption("**Model C: OLS Dosage — Predicting Number of Creators Trusted (Weighted)**")

write_csv(as_tibble(tbl_A), "tables/05/YMRP_ModelA_TrueBeliever_Binary.csv")
write_csv(as_tibble(tbl_C), "tables/05/YMRP_ModelC_Dosage_nTrusted.csv")

cat("Exported: tables/05/ — 2 model CSVs\n")
cat("\n=== File 05 Complete ===\n")