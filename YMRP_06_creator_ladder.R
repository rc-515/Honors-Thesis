# =============================================================================
# YMRP_06_creator_ladder.R
# NEW FILE — covers analyses mentioned in the thesis text that had no code:
#   1. "Recognizing names increased likeliness to vote Trump by 8% per creator"
#   2. "Those who only recognized (not followed) showed no effect"
#   3. "Fans (follow but not trust) are 4.4x more likely to vote Trump"
#   4. "Trusters are 13.1x more likely to vote Trump"
#   5. "Effect on vote SWITCHING" (borderline p=0.054)
# Uses survey weights via svyglm(). Exports tables to Word.
# =============================================================================

source("YMRP_00_setup.R")

CONTROLS <- "faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4"

# =============================================================================
# VARIABLE CONSTRUCTION
# For each creator we have:
#   familiarity_grid_x: 1 = Follow, 2 = Recognize but don't follow, 3 = Unfamiliar
#   trust_grid_x:       1 = Trust, 2 = Follow but skeptical, 3/4 = Not a fan
#
# We build three count variables:
#   n_recognized_only  = count of creators recognized but NOT followed
#   n_followed         = count of creators followed (familiarity == 1)
#   n_trusted          = already built in setup (trust_grid == 1)
# =============================================================================

dat <- dat |>
  mutate(
    # Recognized but not following (familiarity = 2)
    n_recognized_only = rowSums(
      across(all_of(familiarity_cols), ~ .x == 2), na.rm = TRUE
    ),
    # Following (familiarity = 1)
    n_followed = rowSums(
      across(all_of(familiarity_cols), ~ .x == 1), na.rm = TRUE
    ),
    # Binary versions for subgroup models
    any_recognized_only = if_else(n_recognized_only > 0 & n_followed == 0, 1L, 0L),
    any_followed        = if_else(n_followed > 0, 1L, 0L)
  )

# Update the survey design with new variables
svy <- svydesign(ids = ~1, weights = ~weight, data = dat)

# =============================================================================
# MODEL 1: Full recognition ladder — does recognizing, following, or trusting
# predict Trump vote, when entered as counts?
# "Recognition: +8% per creator (p=0.00595)"
# =============================================================================
model_ladder <- svyglm(
  vote_trump_24 ~ n_recognized_only + n_followed + n_trusted +
    faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
  design = svy,
  family  = quasibinomial()
)

cat("\n=== MODEL 1: Recognition Ladder — All Three Levels → Trump Vote ===\n")
summary(model_ladder)
cat("\n--- Odds Ratios ---\n")
print(round(exp(coef(model_ladder)), 3))
cat("\n--- Marginal Effects (Percentage-Point Change per Additional Creator) ---\n")
print(avg_slopes(model_ladder))

# =============================================================================
# MODEL 2: Recognize-only vs follow vs trust — categorical approach
# Three mutually exclusive groups:
#   Group 0: Doesn't recognize any creator
#   Group 1: Recognizes but doesn't follow any
#   Group 2: Follows at least one (but trusts none)
#   Group 3: Trusts at least one
# =============================================================================
dat <- dat |>
  mutate(
    ladder_group = factor(
      case_when(
        n_trusted >= 1                           ~ "3_Trusts",
        n_followed >= 1 & n_trusted == 0         ~ "2_Follows",
        n_recognized_only >= 1 & n_followed == 0 ~ "1_Recognizes",
        TRUE                                     ~ "0_None"
      ),
      levels = c("0_None", "1_Recognizes", "2_Follows", "3_Trusts")
    )
  )

svy <- svydesign(ids = ~1, weights = ~weight, data = dat)

model_ladder_cat <- svyglm(
  vote_trump_24 ~ ladder_group +
    faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
  design = svy,
  family  = quasibinomial()
)

cat("\n=== MODEL 2: Categorical Ladder Groups → Trump Vote ===\n")
summary(model_ladder_cat)
cat("\n--- Odds Ratios (vs. 'Doesn't Recognize Any') ---\n")
print(round(exp(coef(model_ladder_cat)), 3))

# Predicted probabilities for each group — useful for in-text comparisons
cat("\n--- Predicted Probability of Voting Trump by Group ---\n")
preds <- predictions(model_ladder_cat,
                     newdata = datagrid(ladder_group = levels(dat$ladder_group),
                                        faminc5 = mean(dat$faminc5, na.rm = TRUE))) |>
  as_tibble() |>
  select(ladder_group, estimate, conf.low, conf.high) |>
  mutate(across(where(is.numeric), ~ round(.x, 3)))
print(preds)

# =============================================================================
# MODEL 3: VOTE SWITCHING
# Does creator engagement predict switching to Republican in 2024?
# (Borderline effect mentioned in text: p=0.054 for recognition; strong for trust)
# =============================================================================
# Note: vote_switch_to_trump is built in setup (1 = switched to Trump in 2024)
if ("vote_switch_to_trump" %in% names(dat)) {
  model_switch <- svyglm(
    vote_switch_to_trump ~ n_recognized_only + n_followed + n_trusted +
      faminc5 + educ4 + race2 + pid7_with_leaners + urbancity3 + age4,
    design = svy,
    family  = quasibinomial()
  )
  cat("\n=== MODEL 3: Vote Switching → Trump ===\n")
  summary(model_switch)
  cat("\n--- Odds Ratios ---\n")
  print(round(exp(coef(model_switch)), 3))
} else {
  cat("\n[NOTE] 'vote_switch_to_trump' not found in data — skipping Model 3.\n")
}

# =============================================================================
# GRAPHS
# =============================================================================

# Graph: Predicted Trump vote % by ladder group
ggplot(preds, aes(x = ladder_group, y = estimate,
                   ymin = conf.low, ymax = conf.high)) +
  geom_col(fill = "darkred", alpha = 0.8, width = 0.6) +
  geom_errorbar(width = 0.2, color = "black") +
  geom_text(aes(label = scales::percent(estimate, accuracy = 0.1)),
            vjust = -0.6, fontface = "bold") +
  scale_x_discrete(labels = c("Doesn't\nRecognize Any",
                               "Recognizes\n(Doesn't Follow)",
                               "Follows\n(Doesn't Trust)",
                               "Trusts\nat Least One")) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 0.85)) +
  labs(
    title    = "The Engagement Pipeline",
    subtitle = "Predicted probability of voting Trump by level of creator engagement",
    y        = "Predicted Probability (Vote Trump)",
    x        = NULL
  )

ggsave("figures/06/YMRP_Fig_Creator_Ladder.png", width = 7, height = 5, dpi = 300)
cat("Saved: YMRP_Fig_Creator_Ladder.png\n")

# =============================================================================
# GRAPH: Predicted Trump Vote Probability by Engagement Level
# Three lines: Recognizing Only (n_recognized), Following (n_following),
# Trusting (n_trusted) — all as dosage predictors.
# NOTE: Requires n_following column (creators followed but not trusted).
# Add to YMRP_00_setup.R if not present:
#   n_following = rowSums(across(all_of(trust_cols), ~ .x == 2), na.rm = TRUE)
# =============================================================================

get_ladder_preds <- function(xvar, label) {
  grid <- base_controls[rep(1, length(x_seq)), ]
  grid$n_recognized_only <- 0
  grid$n_followed        <- 0
  grid$n_trusted         <- 0
  grid[[xvar]]           <- x_seq
  tibble(
    x    = x_seq,
    fit  = plogis(as.numeric(predict(model_ladder, newdata = grid, type = "link"))),
    type = label
  )
}

engagement_df <- bind_rows(
  get_ladder_preds("n_trusted",         "Trusting"),
  get_ladder_preds("n_followed",        "Following"),
  get_ladder_preds("n_recognized_only", "Recognizing Only")
) |>
  mutate(type = factor(type, levels = c("Recognizing Only", "Following", "Trusting")))

ggplot(engagement_df, aes(x = x, y = fit, color = type, linewidth = type)) +
  geom_line() +
  scale_color_manual(values = engagement_pal, name = "Type") +
  scale_linewidth_manual(values = engagement_lwd, name = "Type") +
  scale_x_continuous(breaks = 0:11, name = "Number of Creators (by Engagement Level)") +
  scale_y_continuous(labels = scales::percent, name = "Predicted Probability") +
  labs(
    caption = "Source: YMRP \u00B7 Controls: income, education, race, party ID, urban/rural, age."
  ) 

ggsave("figures/06/YMRP_Fig_Engagement_TrumpVote.png",
       width = 7.5, height = 5.5, dpi = 300)

# =============================================================================
# EXPORT: Tables to Word
# =============================================================================

tbl1 <- tbl_regression(
  model_ladder,
  exponentiate = TRUE,
  label = list(
    n_recognized_only ~ "# Creators Recognized Only (No Follow)",
    n_followed        ~ "# Creators Followed",
    n_trusted         ~ "# Creators Trusted",
    faminc5           ~ "Family Income (Quintile)",
    educ4             ~ "Education (4-Level)",
    race2             ~ "Race (Binary)",
    pid7_with_leaners ~ "Party ID (3-cat)",
    urbancity3        ~ "Urban/Rural (3-cat)",
    age4              ~ "Age Group"
  )
) |>
  bold_labels() |> bold_p(t = 0.05) |>
  modify_caption("**Table 11: Creator Engagement Ladder — Predicting Trump Vote (Weighted Logistic)**")

tbl2 <- tbl_regression(
  model_ladder_cat,
  exponentiate = TRUE,
  label = list(
    ladder_group      ~ "Engagement Level (Ref: No Recognition)",
    faminc5           ~ "Family Income (Quintile)",
    educ4             ~ "Education (4-Level)",
    race2             ~ "Race (Binary)",
    pid7_with_leaners ~ "Party ID (3-cat)",
    urbancity3        ~ "Urban/Rural (3-cat)",
    age4              ~ "Age Group"
  )
) |>
  bold_labels() |> bold_p(t = 0.05) |>
  modify_caption("**Table 12: Categorical Ladder Groups — Predicting Trump Vote (Weighted Logistic)**")

write_csv(as_tibble(tbl1), "tables/06/YMRP_Model11_CreatorLadder_Counts.csv")
write_csv(as_tibble(tbl2), "tables/06/YMRP_Model12_CreatorLadder_Categorical.csv")

cat("Exported: tables/06/ — 2 model CSVs\n")
