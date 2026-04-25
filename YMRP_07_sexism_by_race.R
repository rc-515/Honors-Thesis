# =============================================================================
# YMRP_07_sexism_by_race.R
# Analysis: Sexism index differences by race; trust level distribution by race.
# Weighted descriptives + ANOVA-style linear model. Exports tables to Word.
# =============================================================================

source("YMRP_00_setup.R")

# Set White as reference category for race_label
dat$race_label <- factor(dat$race_label,
                         levels = c("White", "Black", "Hispanic", "Other/Multiracial"))
svy <- svydesign(ids = ~1, weights = ~weight, data = dat)

# Controls used in all adjusted models
CONTROLS <- "faminc5 + educ4 + pid7_with_leaners + urbancity3 + age4"

# =============================================================================
# A. TRUST LEVELS BY RACE (Weighted Crosstab)
# "The highest concentration of deep trust (3+) is among Black respondents,
#  closely followed by White respondents."
# =============================================================================
cat("\n=== A. Trust Level Distribution by Race (Weighted) ===\n")

# Weighted crosstab using survey design
race_trust_svy <- svytable(~ race_label + trust_level, design = svy)
race_trust_prop <- prop.table(race_trust_svy, margin = 1) * 100  # row percentages

cat("Row percentages (% of each race at each trust level):\n")
print(round(race_trust_prop, 1))

# Unweighted counts for reference
race_trust_raw <- dat |>
  filter(!is.na(race_label), !is.na(trust_level)) |>
  group_by(race_label, trust_level) |>
  summarize(n = n(), .groups = "drop_last") |>
  mutate(pct_of_race = round(n / sum(n) * 100, 1)) |>
  ungroup()

cat("\nUnweighted raw counts:\n")
print(race_trust_raw)

# =============================================================================
# B. AVERAGE SEXISM INDEX BY RACE (Weighted)
# "Black men: mean 3.50; Hispanic: 3.36; White: 3.18; Other: 3.18"
# =============================================================================
cat("\n=== B. Average Sexism Index by Race (Weighted) ===\n")

race_sexism_svy <- svyby(
  ~ sexism_index,
  by     = ~ race_label,
  design = svy,
  FUN    = svymean,
  na.rm  = TRUE
)
cat("Weighted means by race:\n")
print(race_sexism_svy)

# Weighted medians (approximate)
race_sexism_quantiles <- svyby(
  ~ sexism_index,
  by     = ~ race_label,
  design = svy,
  FUN    = svyquantile,
  quantiles = 0.5,
  na.rm  = TRUE,
  keep.names = FALSE
)
cat("\nWeighted medians by race:\n")
print(race_sexism_quantiles)

# =============================================================================
# C. ANOVA — Is race difference statistically significant?
# Using weighted linear model via svyglm
# =============================================================================
cat("\n=== C. Weighted ANOVA: Sexism Index ~ Race ===\n")

# Unadjusted model (descriptive — no controls)
model_race_sexism_unadj <- svyglm(
  sexism_index ~ race_label,
  design = svy,
  family = gaussian()
)
cat("--- Unadjusted model ---\n")
summary(model_race_sexism_unadj)

# Adjusted model (controls for income, education, party ID, urban/rural, age)
model_race_sexism <- svyglm(
  as.formula(paste("sexism_index ~ race_label +", CONTROLS)),
  design = svy,
  family = gaussian()
)
cat("\n--- Adjusted model (full controls) ---\n")
summary(model_race_sexism)

# F-test (ANOVA-style) on adjusted model
cat("\n--- ANOVA-style F-test (adjusted) ---\n")
print(regTermTest(model_race_sexism, ~ race_label))

# =============================================================================
# D. ITEM-BY-ITEM BREAKDOWN BY RACE (Weighted)
# =============================================================================
cat("\n=== D. Item-Level Sexism Scores by Race (Weighted) ===\n")

sexism_items <- c("s1","s2","s3","s4","s5","s6","s7","s8","s9","s10","s11")

item_by_race <- map_dfr(sexism_items, function(item) {
  res <- svyby(
    as.formula(paste0("~", item)),
    by     = ~ race_label,
    design = svy,
    FUN    = svymean,
    na.rm  = TRUE
  )
  res$item <- item
  res
})

print(item_by_race)

# =============================================================================
# GRAPHS
# =============================================================================

# Graph 1: Proportional bar chart — trust levels by race
ggplot(race_trust_raw, aes(x = race_label, y = pct_of_race / 100, fill = trust_level)) +
  geom_col(position = "fill", alpha = 0.85) +
  scale_y_continuous(labels = scales::percent) +
  scale_fill_manual(values = c("gray90", "lightblue", "steelblue", "darkred")) +
  labs(
    title    = "The Multiracial Manosphere",
    subtitle = "Proportion of young men at each trust level, by race",
    y        = "Percentage within racial group",
    x        = NULL,
    fill     = "Creators trusted"
  ) +
  theme(legend.position = "right")

ggsave("figures/07/YMRP_Fig_Trust_by_Race.png", width = 7, height = 5, dpi = 300)

# Graph 2: Violin + boxplot — sexism distribution by race
ggplot(dat |> filter(!is.na(race_label)),
       aes(x    = reorder(race_label, sexism_index, FUN = mean, na.rm = TRUE),
           y    = sexism_index,
           fill = race_label)) +
  geom_violin(alpha = 0.5) +
  geom_boxplot(width = 0.2, color = "black", alpha = 0.8) +
  scale_fill_brewer(palette = "Set2") +
  labs(
    title    = "Baseline Sexism by Race",
    subtitle = "Distribution of the sexism index across racial groups",
    y        = "Sexism Index (5 = High)",
    x        = NULL
  ) +
  theme(legend.position = "none")

ggsave("figures/07/YMRP_Fig_Sexism_by_Race.png", width = 7, height = 5, dpi = 300)

# Graph 3: Dosage staircase faceted by race
ggplot(dat |> filter(!is.na(race_label), !is.na(trust_level)),
       aes(x = trust_level, y = sexism_index, fill = trust_level)) +
  geom_boxplot(alpha = 0.8, outlier.alpha = 0.3) +
  scale_fill_manual(values = c("gray90", "lightblue", "steelblue", "darkred")) +
  facet_wrap(~ race_label, nrow = 1) +
  labs(
    title    = "The Ideological Pipeline Across Demographics",
    subtitle = "Sexism index by trust level, separated by race",
    y        = "Sexism Index (5 = High)",
    x        = "Number of creators trusted",
    fill     = "Trust level"
  ) +
  theme(legend.position = "none",
        strip.text = element_text(face = "bold", size = 11))

ggsave("figures/07/YMRP_Fig_Pipeline_by_Race.png", width = 10, height = 5, dpi = 300)
cat("Saved figures.\n")

# =============================================================================
# EXPORT: Tables to Word
# =============================================================================

# Table: Weighted sexism means by race
sexism_race_df <- as.data.frame(race_sexism_svy) |>
  rename(Race = race_label, `Mean Sexism Index` = sexism_index, `SE` = se) |>
  mutate(across(where(is.numeric), ~ round(.x, 3)))

# Table: Trust level distribution by race
trust_race_wide <- race_trust_raw |>
  select(race_label, trust_level, pct_of_race) |>
  pivot_wider(names_from = trust_level, values_from = pct_of_race, names_prefix = "Trust ") |>
  rename(Race = race_label)

tbl_race_sexism <- tbl_regression(
  model_race_sexism,
  label = list(race_label ~ "Race/Ethnicity")
) |> bold_labels() |> bold_p(t = 0.05)

write_csv(as_tibble(tbl_race_sexism), "tables/07/YMRP_Model7_Sexism_by_Race.csv")
write_csv(sexism_race_df,             "tables/07/YMRP_WeightedMeans_Sexism_by_Race.csv")
write_csv(trust_race_wide,            "tables/07/YMRP_TrustDistribution_by_Race.csv")

cat("Exported: tables/07/ — 3 CSVs\n")