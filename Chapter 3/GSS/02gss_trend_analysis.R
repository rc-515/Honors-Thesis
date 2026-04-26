################################################################################
# GSS 1972-2024 — Tracking Young Men's Political & Social Attitudes Over Time
#
# Uses the GSS CUMULATIVE file to track how young men (18-29) have diverged
# from or converged with the general population across ~50 years of data.
#
# Comparison groups (same as cross-sectional analysis):
#   1. Young Men (18-29)
#   2. Young Women (18-29)
#   3. Older Men (30+)
#   4. Older Women (30+)
#
# Weight: WTSSPS (NORC-recommended for cumulative 1972-2024 analysis)
#
# Thesis angle: do young men's social/political attitudes change in the
# internet era, and is there evidence of divergence from other groups?
################################################################################

# ── 0. Packages ──────────────────────────────────────────────────────────────
required <- c(
  "haven",       # read Stata/SPSS files
  "survey",      # survey-weighted analysis
  "srvyr",       # tidy wrappers for survey pkg
  "tidyverse",   # data wrangling + ggplot2
  "labelled",    # handle haven-labelled columns
  "scales",      # pretty axis labels
  "patchwork",   # combine ggplot panels
  "broom"        # tidy model output
)

for (pkg in required) {
  if (!requireNamespace(pkg, quietly = TRUE)) install.packages(pkg)
  library(pkg, character.only = TRUE)
}

# ── 1. Load GSS cumulative file ─────────────────────────────────────────────
#
# DOWNLOAD INSTRUCTIONS:
#   1. Go to https://gssdataexplorer.norc.org
#   2. Under "Downloads" → download the CUMULATIVE data file (1972-2024)
#      in Stata (.dta) format — the file is ~350 MB
#   3. Place it in your RStudio project directory
#
# *** UPDATE THIS PATH to match your downloaded filename ***

dta_path <- "GSS7224_R1.dta"
# Common alternatives:
# dta_path <- "GSS_cum.dta"
# dta_path <- "gss7224_r1.dta"

# ── 1b. READ ONLY THE COLUMNS WE NEED (critical for memory) ─────────────────
#
# The cumulative file has 6,000+ variables.  Loading all of them will exceed
# R's memory limit.  We use haven's col_select to read ONLY our ~20 columns
# directly from disk — R never sees the other 5,980 columns.

keep_cols <- c(
  # Demographics & weight
  "year", "age", "sex",
  "wtssps", "wtssnrps", "wtssall",
  # Political
  "polviews", "partyid",
  # Trust & wellbeing
  "trust", "happy",
  # Social / cultural
  "fefam", "attend",
  # Confidence in institutions (press & science only — for digital-life connection)
  "conpress", "consci"
)

# Peek at actual column names to determine case (Stata files vary)
all_names <- names(haven::read_dta(dta_path, n_max = 0))
if (all(toupper(keep_cols) %in% toupper(all_names))) {
  # Match case to whatever the file uses
  name_lookup  <- setNames(all_names, toupper(all_names))
  select_these <- unname(name_lookup[toupper(keep_cols)])
  select_these <- select_these[!is.na(select_these)]
} else {
  select_these <- keep_cols
}

cat("Reading", length(select_these), "columns from", dta_path, "...\n")
gss <- haven::read_dta(dta_path, col_select = all_of(select_these))
names(gss) <- toupper(names(gss))

cat("Loaded:", nrow(gss), "respondents across",
    n_distinct(gss$YEAR), "survey waves (",
    ncol(gss), "columns — memory-safe)\n")

# ── 2. Demographics & group construction ─────────────────────────────────────

gss <- gss %>%
  mutate(across(where(is.labelled), ~ as.numeric(.x))) %>%
  mutate(
    age  = AGE,
    male = as.integer(SEX == 1),
    year = YEAR,
    group4 = case_when(
      male == 1 & age >= 18 & age <= 29 ~ "Young Men (18-29)",
      male == 0 & age >= 18 & age <= 29 ~ "Young Women (18-29)",
      male == 1 & age >= 30             ~ "Older Men (30+)",
      male == 0 & age >= 30             ~ "Older Women (30+)",
      TRUE ~ NA_character_
    )
  ) %>%
  filter(!is.na(group4))

# ── 3. Choose weight ────────────────────────────────────────────────────────
#
# WTSSPS is recommended for cumulative (1972-2024) trend analysis.
# It handles sub-sampling, non-response, and post-stratification.

wt_var <- if ("WTSSPS" %in% names(gss)) "WTSSPS" else
  if ("WTSSNRPS" %in% names(gss)) "WTSSNRPS" else "WTSSALL"
cat("Using weight:", wt_var, "\n")

gss <- gss %>%
  rename(wt = all_of(wt_var)) %>%
  mutate(wt = ifelse(is.na(wt) | wt <= 0, NA_real_, wt))


# ══════════════════════════════════════════════════════════════════════════════
#
#       VARIABLE DEFINITIONS — What we're tracking & how we recode
#
# ══════════════════════════════════════════════════════════════════════════════
#
# For clean trend plots, we recode most items into interpretable proportions
# (e.g., "% conservative") or rescaled means. This makes the y-axis intuitive.

gss <- gss %>%
  mutate(
    # ── POLITICAL ──
    
    # POLVIEWS: 1=extremely liberal → 7=extremely conservative
    # → Proportion "conservative" (5, 6, or 7)
    polviews_valid = ifelse(POLVIEWS %in% 1:7, POLVIEWS, NA_real_),
    conservative   = ifelse(polviews_valid >= 5, 1L,
                            ifelse(!is.na(polviews_valid), 0L, NA_integer_)),
    liberal        = ifelse(polviews_valid <= 3, 1L,
                            ifelse(!is.na(polviews_valid), 0L, NA_integer_)),
    
    # PARTYID: 0=strong dem → 6=strong rep (7=other party, drop)
    # → Proportion "Republican-leaning" (4, 5, or 6)
    partyid_valid = ifelse(PARTYID %in% 0:6, PARTYID, NA_real_),
    republican    = ifelse(partyid_valid >= 4, 1L,
                           ifelse(!is.na(partyid_valid), 0L, NA_integer_)),
    independent   = ifelse(partyid_valid == 3, 1L,
                           ifelse(!is.na(partyid_valid), 0L, NA_integer_)),
    
    # ── SOCIAL TRUST & WELLBEING ──
    
    # TRUST: 1=can trust, 2=can't be too careful, 3=depends
    # → Proportion "can trust"
    can_trust = case_when(TRUST == 1 ~ 1L, TRUST %in% 2:3 ~ 0L),
    
    # HAPPY: 1=very happy, 2=pretty happy, 3=not too happy
    # → Proportion "not too happy"
    unhappy = case_when(HAPPY == 3 ~ 1L, HAPPY %in% 1:2 ~ 0L),
    # → Proportion "very happy"
    very_happy = case_when(HAPPY == 1 ~ 1L, HAPPY %in% 2:3 ~ 0L),
    
    # ── SOCIAL/CULTURAL ATTITUDES ──
    
    # FEFAM: 1=strongly agree → 4=strongly disagree
    # "Better if man achieves outside home, woman takes care of home"
    # → Proportion who DISAGREE (3 or 4) = more egalitarian
    fefam_valid   = ifelse(FEFAM %in% 1:4, FEFAM, NA_real_),
    gender_egal   = ifelse(fefam_valid >= 3, 1L,
                           ifelse(!is.na(fefam_valid), 0L, NA_integer_)),
    
    # ATTEND: 0=never → 8=more than once a week
    # → Proportion who NEVER attend (0)
    attend_valid = ifelse(ATTEND %in% 0:8, ATTEND, NA_real_),
    attend_never = ifelse(attend_valid == 0, 1L,
                          ifelse(!is.na(attend_valid), 0L, NA_integer_)),
    
    # ── CONFIDENCE IN INFORMATION SOURCES ──
    # Tracked specifically to test whether distrust of mainstream
    # information institutions relates to digital-life orientation.
    # All coded: 1=great deal, 2=only some, 3=hardly any
    
    no_conf_press    = case_when(
      CONPRESS == 3 ~ 1L, CONPRESS %in% 1:2 ~ 0L),
    hi_conf_science  = case_when(
      CONSCI == 1   ~ 1L, CONSCI  %in% 2:3 ~ 0L)
  )


# ══════════════════════════════════════════════════════════════════════════════
#
#         PART A — COMPUTE WEIGHTED TRENDS BY YEAR × GROUP
#
# ══════════════════════════════════════════════════════════════════════════════

# Define all trend variables and their plot labels
trend_vars <- tribble(
  ~varname,            ~label,                              ~panel,
  # Political ideology & party ID
  "conservative",      "% Conservative (5-7)",              "Political Ideology",
  "liberal",           "% Liberal (1-3)",                   "Political Ideology",
  "republican",        "% Republican-leaning (4-6)",        "Party ID",
  "independent",       "% Independent (pure)",              "Party ID",
  # Trust & wellbeing
  "can_trust",         "% 'Most people can be trusted'",    "Trust & Wellbeing",
  "unhappy",           "% 'Not too happy'",                 "Trust & Wellbeing",
  "very_happy",        "% 'Very happy'",                    "Trust & Wellbeing",
  # Gender, religion & information environment
  "gender_egal",       "% Disagree: man works, woman home", "Gender, Religion & Information",
  "attend_never",      "% Never attend religious services",  "Gender, Religion & Information",
  "no_conf_press",     "% Hardly any confidence: Press",    "Gender, Religion & Information",
  "hi_conf_science",   "% Great deal confidence: Science",  "Gender, Religion & Information"
)

# Compute weighted proportions by year × group for each variable
# Using survey weights properly via srvyr

compute_trend <- function(data, varname) {
  
  d <- data %>%
    filter(!is.na(.data[[varname]]), !is.na(wt)) %>%
    as_survey_design(weights = wt)
  
  d %>%
    group_by(year, group4) %>%
    summarise(
      prop    = survey_mean(.data[[varname]], na.rm = TRUE, vartype = "se"),
      n_cell  = unweighted(n())
    ) %>%
    ungroup() %>%
    mutate(variable = varname)
}

cat("\nComputing weighted trends for", nrow(trend_vars), "variables...\n")
trends <- map_dfr(trend_vars$varname, ~ compute_trend(gss, .x))

# Merge in labels
trends <- trends %>%
  left_join(trend_vars, by = c("variable" = "varname"))

cat("Done. Total trend data points:", nrow(trends), "\n")

# ── Quick diagnostic: how many young men per wave? ──────────────────────────
cell_sizes <- gss %>%
  filter(group4 == "Young Men (18-29)") %>%
  count(year, name = "n_young_men")

cat("\n── Young men (18-29) per GSS wave ──\n")
print(as.data.frame(cell_sizes), row.names = FALSE)


# ══════════════════════════════════════════════════════════════════════════════
#
#                      PART B — TREND VISUALISATIONS
#
# ══════════════════════════════════════════════════════════════════════════════

# Global theme: Times New Roman, larger text throughout
theme_set(
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      panel.grid.minor = element_blank(),
      plot.title       = element_text(face = "bold", size = 22, family = "Times New Roman"),
      plot.subtitle    = element_text(size = 14, colour = "grey40"),
      plot.caption     = element_text(size = 14, family = "Times New Roman"),
      axis.text        = element_text(size = 14),
      axis.title       = element_text(size = 15),
      legend.text      = element_text(size = 13),
      strip.text       = element_text(face = "bold", size = 15)
    )
)

pal <- c(
  "Young Men (18-29)"   = "#E63946",
  "Young Women (18-29)" = "#457B9D",
  "Older Men (30+)"     = "#F4A261",
  "Older Women (30+)"   = "#2A9D8F"
)

# Helper: make a single trend panel (one variable)
plot_trend <- function(data, varname, title, show_legend = FALSE) {
  
  d <- data %>% filter(variable == varname, n_cell >= 15)
  
  if (nrow(d) == 0) return(ggplot() + theme_void() + ggtitle(title))
  
  p <- d %>%
    ggplot(aes(x = year, y = prop, colour = group4, fill = group4)) +
    # Shaded band for internet era
    annotate("rect", xmin = 2000, xmax = max(d$year),
             ymin = -Inf, ymax = Inf,
             fill = "grey90", alpha = 0.4) +
    annotate("text", x = 2000, y = max(d$prop + d$prop_se, na.rm = TRUE),
             label = "Internet era \u2192", hjust = 0, size = 5,
             colour = "grey50", fontface = "italic") +
    geom_line(alpha = 0.3, linewidth = 0.3) +
    geom_smooth(method = "loess", span = 0.45, se = FALSE,
                linewidth = 1.2) +
    scale_colour_manual(values = pal, name = NULL) +
    scale_fill_manual(values = pal, name = NULL) +
    scale_y_continuous(labels = percent_format(accuracy = 1)) +
    labs(title = title, x = NULL, y = NULL) +
    theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      plot.title       = element_text(face = "bold", size = 16, family = "Times New Roman"),
      panel.grid.minor = element_blank(),
      legend.position  = if (show_legend) "bottom" else "none",
      legend.text      = element_text(size = 14, family = "Times New Roman")
    )
  
  return(p)
}

# ── Panel 1: Political ideology & party ID ──────────────────────────────────

p1a <- plot_trend(trends, "conservative", "% Conservative (self-ID 5-7)")
p1b <- plot_trend(trends, "republican",   "% Republican-leaning", show_legend = TRUE)

panel_politics <- (p1a / p1b) +
  plot_annotation(
    title = "Political Attitudes Over Time: Young Men vs. Everyone Else",
    subtitle = "GSS 1972-2024 \u00B7 Loess-smoothed weighted proportions \u00B7 Grey band = internet era (2000+)",
    caption = "Source: GSS Cumulative Data \u00B7 Weight: WTSSPS",
    theme = theme(
      plot.title = element_text(face = "bold", size = 22, family = "Times New Roman"),
      plot.subtitle = element_text(size = 15, colour = "grey40", family = "Times New Roman")
    )
  )

ggsave("05_trend_politics.png", panel_politics,
       width = 9, height = 12, dpi = 300)
cat("\nSaved: 05_trend_politics.png\n")


# ── Panel 2: Social trust & wellbeing ────────────────────────────────────────

p2a <- plot_trend(trends, "can_trust",     "% 'Most people can be trusted'")
p2b <- plot_trend(trends, "unhappy",       "% 'Not too happy'", show_legend = TRUE)

panel_trust <- (p2a / p2b) +
  plot_annotation(
    title = "Social Trust & Happiness: Young Men vs. Everyone Else",
    subtitle = "GSS 1972-2024 \u00B7 Loess-smoothed weighted proportions \u00B7 Grey band = internet era (2000+)",
    caption = "Source: GSS Cumulative Data \u00B7 Weight: WTSSPS",
    theme = theme(
      plot.title = element_text(face = "bold", size = 22, family = "Times New Roman"),
      plot.subtitle = element_text(size = 15, colour = "grey40", family = "Times New Roman")
    )
  )

ggsave("06_trend_trust_happy.png", panel_trust,
       width = 9, height = 12, dpi = 300)
cat("Saved: 06_trend_trust_happy.png\n")


# ── Panel 3: Gender roles & confidence in science ────────────────────────────
# Gender egalitarianism is the strongest divergence finding.
# Science confidence is the counterpoint — young men trust science more
# than other groups even as they distrust the press.

p3a <- plot_trend(trends, "gender_egal",    "% Reject trad. gender roles (FEFAM)")
p3b <- plot_trend(trends, "hi_conf_science","% Great deal confidence: Science",
                  show_legend = TRUE)

panel_social <- (p3a / p3b) +
  plot_annotation(
    title = "Gender Roles & Science Confidence: Young Men vs. Everyone Else",
    subtitle = "GSS 1972-2024 \u00B7 Loess-smoothed weighted proportions \u00B7 Grey band = internet era (2000+)",
    caption = "Source: GSS Cumulative Data \u00B7 Weight: WTSSPS",
    theme = theme(
      plot.title = element_text(face = "bold", size = 22, family = "Times New Roman"),
      plot.subtitle = element_text(size = 15, colour = "grey40", family = "Times New Roman")
    )
  )

ggsave("07_trend_social.png", panel_social,
       width = 9, height = 12, dpi = 300)
cat("Saved: 07_trend_social.png\n")


# ══════════════════════════════════════════════════════════════════════════════
#
#     PART C — DIVERGENCE TESTS: Has the young-male gap widened over time?
#
# ══════════════════════════════════════════════════════════════════════════════
#
# For each attitude, we fit a survey-weighted logistic regression:
#
#   attitude ~ year_centered * young_male + male + age
#
# The key coefficient is the year × young_male INTERACTION.
# A significant interaction means the young male gap is GROWING (or shrinking)
# over time — exactly the "divergence" story your thesis is about.
#
# We restrict to 1990+ to focus on the internet-era trajectory and to avoid
# diluting with decades where "young men" were a different generational cohort.

cat("\n══════════════════════════════════════════════════════════════════\n")
cat("  DIVERGENCE TESTS: year × young_male interactions (1990-2024)\n")
cat("══════════════════════════════════════════════════════════════════\n\n")

gss_modern <- gss %>%
  filter(year >= 1990, !is.na(wt)) %>%
  mutate(
    young_male  = as.integer(group4 == "Young Men (18-29)"),
    year_c      = (year - 2000) / 10   # centered at 2000, scaled by decade
  )

divergence_results <- map_dfr(trend_vars$varname, function(v) {
  
  d <- gss_modern %>%
    filter(!is.na(.data[[v]])) %>%
    select(all_of(v), young_male, male, age, year_c, wt) %>%
    drop_na()
  
  if (nrow(d) < 100 || sum(d$young_male) < 30) {
    return(tibble(variable = v, note = "insufficient data"))
  }
  
  svy_d <- svydesign(ids = ~1, weights = ~wt, data = d)
  
  fml <- as.formula(paste(v, "~ year_c * young_male + male + age"))
  
  fit <- tryCatch(
    svyglm(fml, design = svy_d, family = quasibinomial()),
    error = function(e) NULL
  )
  
  if (is.null(fit)) return(tibble(variable = v, note = "model failed"))
  
  tidy(fit, conf.int = TRUE) %>%
    filter(term == "year_c:young_male") %>%
    mutate(variable = v)
})

# Merge in labels and display
divergence_table <- divergence_results %>%
  left_join(trend_vars, by = c("variable" = "varname")) %>%
  filter(!is.na(estimate)) %>%
  mutate(
    sig         = ifelse(p.value < 0.05, "*", ""),
    direction   = case_when(
      estimate > 0 & p.value < 0.05 ~ "↑ Growing gap (young men increasing)",
      estimate < 0 & p.value < 0.05 ~ "↓ Growing gap (young men decreasing)",
      TRUE                          ~ "— No significant divergence"
    )
  ) %>%
  select(label, estimate, std.error, p.value, sig, direction) %>%
  arrange(p.value)

cat("Key coefficient: year (per decade) × Young Male indicator\n")
cat("Positive = young men trending HIGHER on that measure over time\n")
cat("Negative = young men trending LOWER\n\n")
print(as.data.frame(divergence_table), digits = 3, row.names = FALSE)


# ── 6e. Forest plot of divergence coefficients ──────────────────────────────

if (nrow(divergence_results %>% filter(!is.na(estimate))) > 0) {
  
  p_diverge <- divergence_results %>%
    filter(!is.na(estimate)) %>%
    left_join(trend_vars, by = c("variable" = "varname")) %>%
    mutate(sig = ifelse(p.value < 0.05, "p < .05", "n.s.")) %>%
    ggplot(aes(x = estimate, y = reorder(label, estimate), colour = sig)) +
    geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +
    geom_point(size = 3) +
    geom_errorbarh(aes(xmin = conf.low, xmax = conf.high), height = 0.3) +
    scale_colour_manual(values = c("p < .05" = "#E63946", "n.s." = "grey60"),
                        name = NULL) +
    labs(
      title = "Is the Young Male Gap Growing? (1990-2024)",
      subtitle = paste0(
        "Interaction coefficients: Year (per decade) × Young Male indicator\n",
        "Logistic regression controlling for sex and age · ",
        "Positive = young men trending higher
        over time"
      ),
      x = "Year × Young Male interaction (log-odds per decade)",
      y = NULL,
      caption = "Source: GSS Cumulative Data 1990-2024 · Weight: WTSSPS"
    ) +
    theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      legend.position = "bottom",
      plot.title = element_text(face = "bold", size = 22, family = "Times New Roman")
    )
  
  ggsave("09_divergence_tests.png", p_diverge,
         width = 11, height = 8, dpi = 300)
  cat("\nSaved: 09_divergence_tests.png\n")
}


# ══════════════════════════════════════════════════════════════════════════════
#
#     PART D — YOUNG MEN vs. YOUNG WOMEN: The Gender Gap Among Youth
#
# ══════════════════════════════════════════════════════════════════════════════
#
# A focused comparison: how has the gap WITHIN the 18-29 cohort changed?
# This is the most direct test of whether young men and young women are
# diverging from each other.

cat("\n══════════════════════════════════════════════════════════════════\n")
cat("  YOUTH GENDER GAP: Difference between young men & young women\n")
cat("══════════════════════════════════════════════════════════════════\n\n")

# Compute the M-F gap per year among 18-29s
youth_gap <- trends %>%
  filter(group4 %in% c("Young Men (18-29)", "Young Women (18-29)"),
         n_cell >= 15) %>%
  select(year, group4, variable, label, panel, prop, prop_se) %>%
  pivot_wider(
    names_from  = group4,
    values_from = c(prop, prop_se),
    names_sep   = "_"
  )

# Clean up column names
names(youth_gap) <- gsub("Young Men \\(18-29\\)", "M", names(youth_gap))
names(youth_gap) <- gsub("Young Women \\(18-29\\)", "F", names(youth_gap))

youth_gap <- youth_gap %>%
  mutate(
    gap    = prop_M - prop_F,
    gap_se = sqrt(prop_se_M^2 + prop_se_F^2)
  )

# Plot the gender gap over time for key variables
key_gap_vars <- c("conservative", "republican", "can_trust",
                  "unhappy", "gender_egal", "hi_conf_science")

plot_gap <- function(data, varname, title) {
  
  d <- data %>% filter(variable == varname, !is.na(gap))
  if (nrow(d) < 3) return(ggplot() + theme_void() + ggtitle(title))
  
  ggplot(d, aes(x = year, y = gap)) +
    annotate("rect", xmin = 2000, xmax = max(d$year, na.rm = TRUE),
             ymin = -Inf, ymax = Inf,
             fill = "grey90", alpha = 0.4) +
    geom_hline(yintercept = 0, linetype = "dashed", colour = "grey50") +
    geom_point(colour = "#E63946", size = 2, alpha = 0.5) +
    geom_smooth(method = "loess", span = 0.5, se = TRUE,
                colour = "#E63946", fill = "#E63946", alpha = 0.15,
                linewidth = 1.2) +
    scale_y_continuous(labels = percent_format(accuracy = 1)) +
    labs(title = title, x = NULL,
         y = "Young Men − Young Women") +
    theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      plot.title       = element_text(face = "bold", size = 16, family = "Times New Roman"),
      panel.grid.minor = element_blank()
    )
}

g1 <- plot_gap(youth_gap, "conservative",     "% Conservative")
g2 <- plot_gap(youth_gap, "republican",       "% Republican-leaning")
g3 <- plot_gap(youth_gap, "can_trust",        "% Can trust people")
g4 <- plot_gap(youth_gap, "unhappy",          "% Not too happy")
g5 <- plot_gap(youth_gap, "gender_egal",      "% Reject trad. gender roles")
g6 <- plot_gap(youth_gap, "hi_conf_science",  "% Great conf: Science")

panel_gap <- (g1 | g2) / (g3 | g4) / (g5 | g6) +
  plot_annotation(
    title = "The Youth Gender Gap: Young Men Minus Young Women (18-29)",
    subtitle = paste0(
      "Positive = young men higher than young women · ",
      "Loess-smoothed with 95% CI · Grey band = internet era"
    ),
    caption = "Source: GSS Cumulative Data 1972-2024 · Weight: WTSSPS",
    theme = theme(
      plot.title = element_text(face = "bold", size = 22, family = "Times New Roman"),
      plot.subtitle = element_text(size = 15, colour = "grey40", family = "Times New Roman")
    )
  )

ggsave("10_youth_gender_gap.png", panel_gap,
       width = 12, height = 15, dpi = 300)
cat("Saved: 10_youth_gender_gap.png\n")


# ══════════════════════════════════════════════════════════════════════════════
#
#                     PART E — EXPORT
#
# ══════════════════════════════════════════════════════════════════════════════

cat("\n═══ Writing results to CSV ═══\n")

write_csv(trends, "table_trends_by_year_group.csv")
write_csv(divergence_table, "table_divergence_tests.csv")
write_csv(youth_gap, "table_youth_gender_gap.csv")

cat("Done. CSVs and PNGs saved to working directory.\n")
cat("\nOutput files:\n")
cat("  05_trend_politics.png      — Political ideology & party ID trends\n")
cat("  06_trend_trust_happy.png   — Social trust & happiness trends\n")
cat("  07_trend_social.png        — Gender roles, secularization & information trust\n")
cat("  09_divergence_tests.png    — Forest plot: is the gap widening?\n")
cat("  10_youth_gender_gap.png    — Youth gender gap (M-F) over time\n")

# ══════════════════════════════════════════════════════════════════════════════
#
#                     NOTES FOR THE THESIS
#
# ══════════════════════════════════════════════════════════════════════════════
#
# 1. WEIGHT:
#    WTSSPS is the NORC-recommended weight for cumulative (1972-2024) analysis.
#    It incorporates post-stratification raking and corrects historical ballot/
#    form errors (see GSS Methodological Report 137).
#
# 2. YEAR COVERAGE (selected variables):
#    - POLVIEWS: 1974-2024 (most years)
#    - PARTYID:  1972-2024 (every year)
#    - TRUST:    1972-2024 (not every year; ~25 waves)
#    - HAPPY:    1972-2024 (nearly every year)
#    - FEFAM:    1977-2024 (intermittent)
#    - ATTEND:   1972-2024 (most years)
#    - CONPRESS: 1973-2024 (intermittent)
#    - CONSCI:   1973-2024 (intermittent)
#    Not every variable appears in every wave.  Gaps in the trend lines
#    are expected and are NOT errors — they reflect actual skip years.
#
# 3. CELL SIZES:
#    Young men 18-29 form ~5-10% of each GSS wave.  In a typical wave of
#    ~1,500-3,300 respondents, that's 75-330 young men.  Per-year estimates
#    will be noisy; the loess smoother helps reveal the signal.  The filter
#    n_cell >= 15 drops years where the subgroup is too thin.
#
# 4. MODE EFFECTS:
#    GSS 2021 was web-only (COVID), and 2022/2024 are mixed-mode.  Some
#    variables (especially TRUST) show mode sensitivity.
#    NORC flags this in the codebook.  Interpret 2021+ data with care,
#    especially for trend breaks that coincide with the mode change.
#
# 5. LINKING TO CROSS-SECTIONAL ANALYSIS:
#    This trend file documents HOW attitudes are changing over time.
#    Your ISSP Digital Societies cross-section (Script 1) documents WHAT
#    young men's digital habits look like in 2024.  Together they support
#    the argument: "young men have diverged on [X attitudes] during the
#    same period that digital habits [Y] became dominant."  This is a
#    correlational observation, not causal proof — but it strengthens
#    the narrative substantially.
#
# 6. THE DIVERGENCE TEST (Part C):
#    The year × young_male interaction is the formal test of whether the
#    gap is widening.  It's estimated over 1990-2024 to focus on the
#    internet-relevant period.  Year is scaled per-decade and centered at
#    2000, so the coefficient reads as "change in log-odds per decade for
#    young men relative to everyone else."
################################################################################