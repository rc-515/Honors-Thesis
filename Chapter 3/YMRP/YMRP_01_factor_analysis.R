# =============================================================================
# YMRP_01_factor_analysis.R
# Factor analysis and reliability testing for the sexism and racism batteries.
# Exports loading tables to Word using gt::gtsave() (matches advisor's style).
# =============================================================================

source("YMRP_00_setup.R")

# =============================================================================
# SEXISM BATTERY
# =============================================================================

sexism_matrix <- dat |>
  select(s1:s11) |>
  drop_na()

cat("\n=== SEXISM BATTERY ===\n")

# --- Reliability (Cronbach's Alpha) ------------------------------------------
cat("\n--- Cronbach's Alpha ---\n")
alpha_sexism <- psych::alpha(sexism_matrix)
print(alpha_sexism$total)

cat("\n--- Alpha If Item Dropped ---\n")
print(alpha_sexism$alpha.drop)

# --- PCA: 1-Factor Solution --------------------------------------------------
cat("\n--- PCA: 1-Factor Solution ---\n")
pca_1f <- psych::principal(sexism_matrix, nfactors = 1)
print(pca_1f$loadings)

# --- PCA: 2-Factor Exploratory -----------------------------------------------
cat("\n--- PCA: 2-Factor Solution (Varimax) ---\n")
pca_2f <- psych::principal(sexism_matrix, nfactors = 2, rotate = "varimax")
print(pca_2f$loadings)

# =============================================================================
# RACISM BATTERY
# =============================================================================

racism_matrix <- dat |>
  select(r1, r2, r3) |>
  drop_na()

cat("\n\n=== RACISM BATTERY ===\n")

# --- Reliability -------------------------------------------------------------
cat("\n--- Cronbach's Alpha ---\n")
alpha_racism <- psych::alpha(racism_matrix)
print(alpha_racism$total)
print(alpha_racism$alpha.drop)

# --- PCA ---------------------------------------------------------------------
cat("\n--- PCA: 1-Factor Solution ---\n")
pca_racism <- psych::principal(racism_matrix, nfactors = 1)
print(pca_racism$loadings)

# =============================================================================
# BUILD EXPORT DATA FRAMES
# =============================================================================

sexism_item_labels <- c(
  "s1: Guys can't speak their minds",
  "s2: Society looks down on masculine men",
  "s3: Men breadwinner / women home",
  "s4: Women should hold more power (reversed)",
  "s5: Feminism favors women over men",
  "s6: Men should be valued more in society",
  "s7: Media is biased towards men (reversed)",
  "s8: Roles only men can do",
  "s9: Roles only women can do",
  "s10: Gay men aren't really men",
  "s11: Trans men aren't really men"
)

racism_item_labels <- c(
  "r1: White privilege exists (reversed)",
  "r2: Racial problems are rare",
  "r3: Society provokes / reverse racism"
)

# 1-factor sexism loadings
sexism_df <- data.frame(
  Item        = sexism_item_labels,
  Loading     = round(as.numeric(pca_1f$loadings[, 1]), 3),
  Communality = round(pca_1f$communality, 3),
  Uniqueness  = round(pca_1f$uniquenesses, 3)
)

# 2-factor sexism loadings
sexism_2f_df <- data.frame(
  Item                    = sexism_item_labels,
  RC1_Traditional_Hostile = round(as.numeric(pca_2f$loadings[, 1]), 3),
  RC2_Feminist_Grievance  = round(as.numeric(pca_2f$loadings[, 2]), 3),
  Communality             = round(pca_2f$communality, 3)
)

# racism loadings
racism_df <- data.frame(
  Item        = racism_item_labels,
  Loading     = round(as.numeric(pca_racism$loadings[, 1]), 3),
  Communality = round(pca_racism$communality, 3),
  Uniqueness  = round(pca_racism$uniquenesses, 3)
)

# =============================================================================
# EXPORT TO CSV
# =============================================================================

write_csv(sexism_df, "tables/01/YMRP_Appendix_Sexism_1Factor.csv")
cat("Exported: YMRP_Appendix_Sexism_1Factor.csv\n")
cat(sprintf("  Cronbach's alpha = %.3f  |  Variance explained = %.1f%%\n",
            alpha_sexism$total$raw_alpha,
            pca_1f$Vaccounted["Proportion Var", 1] * 100))

write_csv(sexism_2f_df, "tables/01/YMRP_Appendix_Sexism_2Factor.csv")
cat("Exported: YMRP_Appendix_Sexism_2Factor.csv\n")
cat(sprintf("  Variance explained: RC1 = %.1f%%  |  RC2 = %.1f%%  |  Total = %.1f%%\n",
            pca_2f$Vaccounted["Proportion Var", 1] * 100,
            pca_2f$Vaccounted["Proportion Var", 2] * 100,
            sum(pca_2f$Vaccounted["Proportion Var", ]) * 100))

write_csv(racism_df, "tables/01/YMRP_Appendix_Racism_FactorAnalysis.csv")
cat("Exported: YMRP_Appendix_Racism_FactorAnalysis.csv\n")
cat(sprintf("  Cronbach's alpha = %.3f  |  Variance explained = %.1f%%\n",
            alpha_racism$total$raw_alpha,
            pca_racism$Vaccounted["Proportion Var", 1] * 100))
