# =============================================================================
# YMRP_03_trust_vs_racism_graphs.R
# Graph export only — replaces theme_nice() with Times New Roman theme
# matching the GSS 2024 analysis file formatting conventions.
# Assumes models (model_mobilize_r3, model_mobilize_r2, mob_sex, mob_r3,
# mob_r2) and dat are already in the environment from YMRP_03_trust_vs_racism.R
# =============================================================================


# ── Fixed control values for prediction grids ────────────────────────────────
faminc_mean <- mean(dat$faminc5,     na.rm = TRUE)
educ_mode   <- as.integer(names(sort(table(dat$educ4),             decreasing = TRUE)[1]))
race_mode   <- as.integer(names(sort(table(dat$race2),             decreasing = TRUE)[1]))
pid_mode    <- names(sort(table(dat$pid7_with_leaners), decreasing = TRUE))[1]
urban_mode  <- names(sort(table(dat$urbancity3),        decreasing = TRUE))[1]
age_mode    <- as.integer(names(sort(table(dat$age4),              decreasing = TRUE)[1]))

# =============================================================================
# GRAPH 1: Racial Grievance Mobilization (r3 × Trust → Trump Vote)
# =============================================================================

r3_seq <- seq(1, 5, length.out = 100)

g_r3 <- expand.grid(
  r3                = r3_seq,
  is_truster_binary = c("Non-Truster", "Truster"),
  faminc5           = faminc_mean,
  educ4             = educ_mode,
  race2             = race_mode,
  pid7_with_leaners = pid_mode,
  urbancity3        = urban_mode,
  age4              = age_mode,
  stringsAsFactors  = FALSE
)

g_r3$pid7_with_leaners <- factor(g_r3$pid7_with_leaners, levels = levels(dat$pid7_with_leaners))
g_r3$urbancity3        <- factor(g_r3$urbancity3,        levels = levels(dat$urbancity3))
g_r3$is_truster_binary <- factor(g_r3$is_truster_binary, levels = levels(dat$is_truster_binary))
g_r3$fit               <- plogis(as.numeric(predict(model_mobilize_r3,
                                                    newdata = g_r3, type = "link")))
g_r3$trust_label       <- factor(g_r3$is_truster_binary,
                                 levels = c("Non-Truster", "Truster"))

p_r3 <- ggplot(g_r3, aes(x = r3, y = fit, colour = trust_label)) +
  geom_line(linewidth = 1.2) +
  scale_colour_manual(
    values = c("Non-Truster" = "gray50", "Truster" = "darkorange")
  ) +
  scale_x_continuous(
    breaks = 1:5,
    labels = c("1\nStrongly\nDisagree", "2", "3\nNeutral", "4", "5\nStrongly\nAgree")
  ) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1)) +
  labs(
    title    = "Weaponizing Grievance",
    subtitle = "Predicted probability of voting Trump by racial grievance score and creator trust",
    y        = "Predicted Probability (Vote Trump)",
    x        = "Belief in Reverse Racism / Special Treatment",
    colour   = "Trusts Creators?",
    caption  = "Source: YMRP \u00B7 Controls: income, education, race, party ID, urban/rural, age."
  ) +
  theme(legend.position = "bottom")

ggsave("figures/03/YMRP_Fig_Racism_Mobilization_r3.png",
       p_r3, width = 7.5, height = 5.5, dpi = 300)
cat("Saved: YMRP_Fig_Racism_Mobilization_r3.png\n")

# =============================================================================
# GRAPH 2: Racism-Is-Rare Mobilization (r2 × Trust → Trump Vote)
# =============================================================================

r2_seq <- seq(1, 5, length.out = 100)

g_r2 <- expand.grid(
  r2                = r2_seq,
  is_truster_binary = c("Non-Truster", "Truster"),
  faminc5           = faminc_mean,
  educ4             = educ_mode,
  race2             = race_mode,
  pid7_with_leaners = pid_mode,
  urbancity3        = urban_mode,
  age4              = age_mode,
  stringsAsFactors  = FALSE
)

g_r2$pid7_with_leaners <- factor(g_r2$pid7_with_leaners, levels = levels(dat$pid7_with_leaners))
g_r2$urbancity3        <- factor(g_r2$urbancity3,        levels = levels(dat$urbancity3))
g_r2$is_truster_binary <- factor(g_r2$is_truster_binary, levels = levels(dat$is_truster_binary))
g_r2$fit               <- plogis(as.numeric(predict(model_mobilize_r2,
                                                    newdata = g_r2, type = "link")))
g_r2$trust_label       <- factor(g_r2$is_truster_binary,
                                 levels = c("Non-Truster", "Truster"))

p_r2 <- ggplot(g_r2, aes(x = r2, y = fit, colour = trust_label)) +
  geom_line(linewidth = 1.2) +
  scale_colour_manual(
    values = c("Non-Truster" = "gray50", "Truster" = "steelblue")
  ) +
  scale_x_continuous(
    breaks = 1:5,
    labels = c("1\nStrongly\nDisagree", "2", "3\nNeutral", "4", "5\nStrongly\nAgree")
  ) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1)) +
  labs(
    title    = "Overriding Racial Reality",
    subtitle = "Predicted probability of voting Trump by \u2018racism is rare\u2019 belief and creator trust",
    y        = "Predicted Probability (Vote Trump)",
    x        = "Believes Racism is Rare",
    colour   = "Trusts Creators?",
    caption  = "Source: YMRP \u00B7 Controls: income, education, race, party ID, urban/rural, age."
  ) +
  theme(legend.position = "bottom")

ggsave("figures/03/YMRP_Fig_Racism_Mobilization_r2.png",
       p_r2, width = 7.5, height = 5.5, dpi = 300)
cat("Saved: YMRP_Fig_Racism_Mobilization_r2.png\n")

# =============================================================================
# GRAPH 3: Attitude Conversion Comparison
# (Sexism index, r3, r2 → predicted Trump vote probability across 1-5 scale)
# =============================================================================

svyglm_predict_logit <- function(model, newdata) {
  eta <- as.numeric(predict(model, newdata = newdata, type = "link"))
  tibble(fit = plogis(eta))
}

x_seq <- seq(1, 5, length.out = 100)

make_grid_03 <- function(att_col) {
  data.frame(
    faminc5           = faminc_mean,
    educ4             = educ_mode,
    race2             = race_mode,
    pid7_with_leaners = factor(pid_mode,   levels = levels(dat$pid7_with_leaners)),
    urbancity3        = factor(urban_mode, levels = levels(dat$urbancity3)),
    age4              = age_mode
  ) |>
    slice(rep(1, length(x_seq))) |>
    mutate(!!att_col := x_seq)
}

get_preds_03 <- function(model, att_col, att_label) {
  grid <- make_grid_03(att_col)
  tibble(
    x        = x_seq,
    attitude = att_label,
    fit      = svyglm_predict_logit(model, grid)$fit
  )
}

plot_df <- bind_rows(
  get_preds_03(mob_sex, "sexism_index", "Sexism Index"),
  get_preds_03(mob_r3,  "r3",           "Racial Grievance (r3)"),
  get_preds_03(mob_r2,  "r2",           "Racism Is Rare (r2)")
) |>
  mutate(attitude = factor(attitude,
                           levels = c("Sexism Index",
                                      "Racial Grievance (r3)",
                                      "Racism Is Rare (r2)")))

p_compare <- ggplot(plot_df, aes(x = x, y = fit, colour = attitude)) +
  geom_line(linewidth = 1.2) +
  scale_colour_manual(
    values = c("darkred", "darkorange", "steelblue")
  ) +
  scale_x_continuous(
    breaks = 1:5,
    labels = c("1\nStrongly\nDisagree", "2", "3\nNeutral", "4", "5\nStrongly\nAgree"),
    name   = "Attitude Score (1\u20135 Likert scale, same for all attitudes)"
  ) +
  scale_y_continuous(
    labels = scales::percent,
    name   = "Predicted Probability (Vote Trump)"
  ) +
  labs(
    title    = "Which Attitude Converts Most Strongly Into Trump Votes?",
    subtitle = "Predicted Trump vote probability by raw attitude score (among 2024 voters)",
    colour   = NULL,
    caption  = "Source: YMRP \u00B7 Controls: income, education, race, party ID, urban/rural, age."
  ) +
  theme(legend.position = "bottom")

ggsave("figures/03/YMRP_Fig_AttitudeConversion_Comparison.png",
       p_compare, width = 7.5, height = 5.5, dpi = 300)
cat("Saved: figures/03/YMRP_Fig_AttitudeConversion_Comparison.png\n\n")