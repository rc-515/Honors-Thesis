# =============================================================================
# YMRP_02_trust_vs_sexism.R
# Models: (1) Dosage — creator trust predicts sexism index
#         (2) Mobilization — sexism × trust (binary) on Trump vote
#         (3) Mobilization — sexism × trust (count/dosage) on Trump vote
#         (4) Mobilization — same models on vote_trump_new_24 (switchers)
# Uses survey weights via svyglm(). Exports tables to Word.
# =============================================================================

source("YMRP_00_setup.R")

# =============================================================================
# MODEL 1: DOSAGE EFFECT
# Does trusting more creators predict a higher sexism index?
# OLS via svyglm (Gaussian family = weighted linear regression)
# =============================================================================
model_dosage_sexism <- svyglm(
  sexism_index ~ n_trusted + faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
  design = svy,
  family  = gaussian()
)

cat("\n=== MODEL 1: Dosage Effect on Sexism Index ===\n")
summary(model_dosage_sexism)

# =============================================================================
# MODEL 2: MOBILIZATION — BINARY TRUST INTERACTION
# Does being a truster shift/amplify the sexism → Trump vote relationship?
# is_truster_binary: Non-Truster (ref) vs. Truster
# =============================================================================
model_mobilize_binary <- svyglm(
  vote_trump_24 ~ sexism_index * is_truster_binary + faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
  design = svy,
  family  = quasibinomial()
)

cat("\n=== MODEL 2: Mobilization — Sexism × Trust (Binary) → Trump Vote ===\n")
summary(model_mobilize_binary)
cat("\n--- Odds Ratios ---\n")
print(round(exp(coef(model_mobilize_binary)), 3))

# =============================================================================
# MODEL 3: MOBILIZATION — COUNT TRUST INTERACTION (DOSE-RESPONSE CHECK)
# Replaces the binary with n_trusted (0, 1, 2, 3...) to test whether
# trusting MORE creators produces a stronger effect — a cleaner test of
# whether the relationship is truly about creator exposure, not just
# self-selection into the "truster" category.
# =============================================================================
model_mobilize_count <- svyglm(
  vote_trump_24 ~ sexism_index * n_trusted + faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
  design = svy,
  family  = quasibinomial()
)

cat("\n=== MODEL 3: Mobilization — Sexism × Trust (Count) → Trump Vote ===\n")
summary(model_mobilize_count)
cat("\n--- Odds Ratios ---\n")
print(round(exp(coef(model_mobilize_count)), 3))

# =============================================================================
# MODEL 4: SAME AS MODEL 2 BUT OUTCOME = vote_trump_new_24
# Tests whether the sexism × trust effect holds specifically for NEW Trump
# voters (switchers + newly mobilized nonvoters), not just loyal Trump voters.
# If this effect is similar to Model 2, creators aren't just activating the
# existing base — they're bringing in genuinely new voters.
# =============================================================================
model_mobilize_switchers <- svyglm(
  vote_trump_new_24 ~ sexism_index * is_truster_binary + faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
  design = svy,
  family  = quasibinomial()
)

cat("\n=== MODEL 4: Mobilization — Sexism × Trust → New/Switched Trump Vote ===\n")
summary(model_mobilize_switchers)
cat("\n--- Odds Ratios ---\n")
print(round(exp(coef(model_mobilize_switchers)), 3))

# =============================================================================
# RAW NUMBERS: Trump vote rate by sexism level (Trusters only)
# Unweighted descriptive — shows the raw staircase pattern before modeling
# =============================================================================
cat("\n=== Raw: Trump Vote % by Sexism Level (Trusters Only) ===\n")
staircase_data <- dat |>
  filter(is_truster_binary == "Truster",
         !is.na(sexism_index), !is.na(vote_trump_24)) |>
  mutate(sexism_bucket = round(sexism_index)) |>
  group_by(sexism_bucket) |>
  summarize(
    n         = n(),
    pct_trump = round(mean(vote_trump_24) * 100, 1)
  ) |>
  arrange(sexism_bucket)

print(staircase_data)

# =============================================================================
# GRAPHS
# =============================================================================

# Graph 1: Predicted Probability — Binary Trust Interaction
plot_predictions(model_mobilize_binary,
                 condition = c("sexism_index", "is_truster_binary")) +
  scale_color_manual(values = c("gray50", "darkred")) +
  scale_fill_manual(values  = c("gray50", "darkred")) +
  scale_y_continuous(labels = scales::percent) +
  labs(
    title    = "Weaponizing Sexism",
    subtitle = "Predicted probability of voting Trump by sexism score and creator trust",
    y        = "Predicted Probability (Vote Trump)",
    x        = "Sexism Index (5 = High)",
    color    = "Trusts Creators?",
    fill     = "Trusts Creators?"
  ) 

ggsave("figures/02/YMRP_Fig_Sexism_Mobilization.png", width = 7, height = 5, dpi = 300)
cat("Saved: YMRP_Fig_Sexism_Mobilization.png\n")

# Graph 2: Predicted Probability — Count Trust Interaction
# Shows dose-response: one line per trust level (0, 1, 2, 3+)
plot_predictions(model_mobilize_count,
                 condition = c("sexism_index", "n_trusted"),
                 variables = list(n_trusted = 0:3)) +
  scale_y_continuous(labels = scales::percent) +
  labs(
    title    = "Dose-Response: Creator Trust and Sexism → Trump Vote",
    subtitle = "Predicted Trump vote probability by sexism score and number of creators trusted",
    y        = "Predicted Probability (Vote Trump)",
    x        = "Sexism Index (5 = High)",
    color    = "# Creators Trusted",
    fill     = "# Creators Trusted"
  ) 

ggsave("figures/02/YMRP_Fig_Sexism_CountInteraction.png", width = 7, height = 5, dpi = 300)
cat("Saved: YMRP_Fig_Sexism_CountInteraction.png\n")

# =============================================================================
# GRAPH: Sexism Index Distribution by Fan Status
# Violin + boxplot showing spread of sexism scores across Non-Fan,
# Skeptical Fan, and True Believer groups.
# =============================================================================

# Palette matched to graph (red, green, blue with transparency)
fan_pal <- c(
  "Non-Fan"       = "#E06B6B",
  "Skeptical Fan" = "#6BAA6B",
  "True Believer" = "#6B9FD4"
)

# Weighted n for caption
n_total <- sum(!is.na(dat$sexism_index) & !is.na(dat$fan_status))

ggplot(
  dat |> filter(!is.na(sexism_index), !is.na(fan_status)),
  aes(x = fan_status, y = sexism_index, fill = fan_status, color = fan_status)
) +
  geom_violin(
    alpha       = 0.35,
    trim        = FALSE,
    linewidth   = 0.55,
    color = "black"
  ) +
  geom_boxplot(
    width     = 0.18,
    alpha     = 0.75,
    linewidth = 0.55,
    outlier.size  = 1.2,
    outlier.alpha = 0.5,
    color = "black"
  ) +
  scale_fill_manual(values  = fan_pal, guide = "none") +
  scale_color_manual(values = fan_pal, guide = "none") +
  scale_y_continuous(
    breaks = 1:5,
    limits = c(1, 5)
  ) +
  scale_x_discrete(
    labels = c(
      "Non-Fan"       = "Non-Fan",
      "Skeptical Fan" = "Skeptical Fan",
      "True Believer" = "True Believer"
    )
  ) +
  labs(
    title   = NULL,
    x       = NULL,
    y       = "Sexism Index (5 = High Sexism)",
    caption = paste0(
      "Source: YMRP"
    )
  ) +
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
  theme(
    axis.text.x        = element_text(size = 16),
  )

ggsave("figures/02/YMRP_Fig_Sexism_by_FanStatus.png",
       width = 7, height = 6, dpi = 300)
cat("Saved: YMRP_Fig_Sexism_by_FanStatus.png\n")

# =============================================================================
# GRAPH: Predicted Trump Vote Probability by Engagement Level
# Three lines: Recognizing Only (n_recognized), Following (n_following),
# Trusting (n_trusted) — all as dosage predictors.
# NOTE: Requires n_following column (creators followed but not trusted).
# Add to YMRP_00_setup.R if not present:
#   n_following = rowSums(across(all_of(trust_cols), ~ .x == 2), na.rm = TRUE)
# =============================================================================

x_seq       <- 0:11
faminc_mean <- mean(dat$faminc5,  na.rm = TRUE)
educ_mode   <- as.integer(names(sort(table(dat$educ4),             decreasing = TRUE)[1]))
race_mode   <- as.integer(names(sort(table(dat$race2),             decreasing = TRUE)[1]))
pid_mode    <- names(sort(table(dat$pid7_with_leaners), decreasing = TRUE))[1]
urban_mode  <- names(sort(table(dat$urbancity3),        decreasing = TRUE))[1]
age_mode    <- as.integer(names(sort(table(dat$age4),              decreasing = TRUE)[1]))

base_controls <- data.frame(
  faminc5           = faminc_mean,
  educ4             = educ_mode,
  race2             = race_mode,
  pid7_with_leaners = factor(pid_mode,   levels = levels(dat$pid7_with_leaners)),
  urbancity3        = factor(urban_mode, levels = levels(dat$urbancity3)),
  age4              = age_mode
)

# Fit the three dosage models
model_eng_trust <- svyglm(
  as.formula(paste("vote_trump_24 ~ n_trusted +", CONTROLS)),
  design = svy, family = quasibinomial()
)
model_eng_follow <- svyglm(
  as.formula(paste("vote_trump_24 ~ n_following +", CONTROLS)),
  design = svy, family = quasibinomial()
)
model_eng_recog <- svyglm(
  as.formula(paste("vote_trump_24 ~ n_recognized +", CONTROLS)),
  design = svy, family = quasibinomial()
)

get_engagement_preds <- function(model, xvar, label) {
  grid <- base_controls[rep(1, length(x_seq)), ]
  grid[[xvar]] <- x_seq
  tibble(
    x    = x_seq,
    fit  = plogis(as.numeric(predict(model, newdata = grid, type = "link"))),
    type = label
  )
}

engagement_df <- bind_rows(
  get_engagement_preds(model_eng_trust,  "n_trusted",    "Trusting"),
  get_engagement_preds(model_eng_follow, "n_following",  "Following"),
  get_engagement_preds(model_eng_recog,  "n_recognized", "Recognizing Only")
) |>
  mutate(type = factor(type, levels = c("Recognizing Only", "Following", "Trusting")))

engagement_pal <- c(
  "Recognizing Only" = "grey60",
  "Following"        = "#E8888A",
  "Trusting"         = "#8B1A1A"
)
engagement_lwd <- c(
  "Recognizing Only" = 1.0,
  "Following"        = 1.4,
  "Trusting"         = 1.4
)

ggplot(engagement_df, aes(x = x, y = fit, color = type, linewidth = type)) +
  geom_line() +
  scale_color_manual(values = engagement_pal, name = "Type") +
  scale_linewidth_manual(values = engagement_lwd, name = "Type") +
  scale_x_continuous(breaks = 0:11, name = "Number of Creators (by Engagement Level)") +
  scale_y_continuous(labels = scales::percent, name = "Predicted Probability") +
  labs(
    title   = NULL,
    caption = "Weighted logistic regression (svyglm). Controls: income, education, race, party ID, urbanicity, age."
  ) +
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
  theme(
    panel.grid.minor   = element_blank(),
    plot.caption       = element_text(size = 10, colour = "grey40", hjust = 0),
    axis.text          = element_text(size = 13),
    axis.title         = element_text(size = 14),
    legend.text        = element_text(size = 13),
    legend.title       = element_text(size = 13, face = "bold"),
    legend.position    = c(0.85, 0.5),
    plot.margin        = margin(t = 10, r = 80, b = 5, l = 5, unit = "pt")
  )

ggsave("figures/02/YMRP_Fig_Engagement_TrumpVote.png",
       width = 7.5, height = 5.5, dpi = 300)
cat("Saved: YMRP_Fig_Engagement_TrumpVote.png\n")


# =============================================================================
# GRAPH: Sexism Index vs. Number of Creators Trusted (scatter + OLS line)
# Unweighted descriptive. Jitter applied for visibility.
# =============================================================================

set.seed(42)

ggplot(
  dat |> filter(!is.na(sexism_index), !is.na(n_trusted)),
  aes(x = n_trusted, y = sexism_index)
) +
  geom_jitter(
    width  = 0.25,
    height = 0.05,
    alpha  = 0.35,
    size   = 1.6,
    color  = "grey50"
  ) +
  geom_smooth(
    method    = "lm",
    se        = TRUE,
    color     = "#8B1A1A",
    fill      = "#E8888A",
    alpha     = 0.25,
    linewidth = 1.4
  ) +
  scale_x_continuous(breaks = 0:11, name = "Number of Creators Trusted (0 to 11)") +
  scale_y_continuous(breaks = 1:5,  limits = c(1, 5),
                     name = "Sexism Index (5 = High)") +
  labs(
    title   = NULL,
    caption = "Source: YMRP \u00B7 Line = OLS best fit \u00B7 Jitter applied for visibility."
  ) 

ggsave("figures/02/YMRP_Fig_Sexism_by_nTrusted.png",
       width = 7.5, height = 5.5, dpi = 300)
cat("Saved: YMRP_Fig_Sexism_by_nTrusted.png\n")


# =============================================================================
# EXPORT: Regression Tables to CSV
# =============================================================================

tbl1 <- tbl_regression(
  model_dosage_sexism,
  label = list(
    n_trusted ~ "Number of Creators Trusted",
    faminc5   ~ "Family Income (Quintile)",
    race2     ~ "Race (Binary)",
    educ4     ~ "Education (4-Level)"
  )
) |> bold_labels() |> bold_p(t = 0.05)

tbl2 <- tbl_regression(
  model_mobilize_binary,
  exponentiate = TRUE,
  label = list(
    sexism_index              ~ "Sexism Index",
    is_truster_binary         ~ "Trusts Creators (Binary)",
    `sexism_index:is_truster_binary` ~ "Interaction: Sexism × Trusts Creators",
    faminc5                   ~ "Family Income (Quintile)"
  )
) |> bold_labels() |> bold_p(t = 0.05)

tbl3 <- tbl_regression(
  model_mobilize_count,
  exponentiate = TRUE,
  label = list(
    sexism_index            ~ "Sexism Index",
    n_trusted               ~ "Number of Creators Trusted",
    `sexism_index:n_trusted` ~ "Interaction: Sexism × # Creators Trusted",
    faminc5                 ~ "Family Income (Quintile)"
  )
) |> bold_labels() |> bold_p(t = 0.05)

tbl4 <- tbl_regression(
  model_mobilize_switchers,
  exponentiate = TRUE,
  label = list(
    sexism_index              ~ "Sexism Index",
    is_truster_binary         ~ "Trusts Creators (Binary)",
    `sexism_index:is_truster_binary` ~ "Interaction: Sexism × Trusts Creators",
    faminc5                   ~ "Family Income (Quintile)"
  )
) |> bold_labels() |> bold_p(t = 0.05)

# Export each model as its own CSV
write_csv(as_tibble(tbl1), "tables/02/YMRP_Model1_Dosage_Sexism.csv")
write_csv(as_tibble(tbl2), "tables/02/YMRP_Model2_Mobilize_Binary.csv")
write_csv(as_tibble(tbl3), "tables/02/YMRP_Model3_Mobilize_Count.csv")
write_csv(as_tibble(tbl4), "tables/02/YMRP_Model4_Mobilize_Switchers.csv")

cat("Exported: tables/02/ — 4 model CSVs\n")