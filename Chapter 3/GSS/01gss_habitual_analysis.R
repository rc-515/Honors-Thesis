################################################################################
# GSS 2024 — Young Men vs. the Rest: Digital Life, Tech, & Political Attitudes
# 
# ISSP "Digital Societies" module (first fielded in 2024)
# All analyses use WTSSNRPS (recommended weight for 2024 cross-section)
#
# Comparison groups:
#   1. Young men aged 18-29   ("Young Men")
#   2. All respondents         ("General Pop.")
#   3. All aged 18-29          ("All Youth")
#   4. Men of all ages         ("All Men")
#
# Outputs: weighted descriptive tables, diverging-bar charts, forest plot of
#          logistic regression coefficients predicting "Young Male 18-29"
################################################################################

# ── 0. Packages ──────────────────────────────────────────────────────────────
required <- c(
  "haven",       # read Stata/SPSS data files
  "survey",      # survey-weighted analysis
  "srvyr",       # tidy wrappers for survey pkg
  "tidyverse",   # data wrangling + ggplot2
  "labelled",    # handle haven-labelled columns
  "scales",      # pretty axis labels
  "patchwork",   # combine ggplot panels
  "broom",       # tidy model output
  "MASS"         # polr() for ordinal regression
)

for (pkg in required) {
  if (!requireNamespace(pkg, quietly = TRUE)) install.packages(pkg)
  library(pkg, character.only = TRUE)
}

# ── 1. Load & prepare data ──────────────────────────────────────────────────
#
# DOWNLOAD INSTRUCTIONS:
#   1. Go to https://gssdataexplorer.norc.org
#   2. Create a free account (or log in)
#   3. Under "Downloads" → download the 2024 cross-section data file
#      in Stata (.dta) or SPSS (.sav) format
#   4. Place the file in your RStudio project directory (or set the path below)
#
# *** UPDATE THIS PATH to wherever you saved the downloaded file ***

gss_all <- haven::read_dta("GSS2024.dta")
# If you downloaded SPSS format instead, use:
# gss_all <- haven::read_sav("GSS2024.sav")

# Quick check the key variables exist
key_vars <- c(
  # Digital life & tech orientation
  "INTRNETUSE", "INTGAME", "INTSTREAM", "INTSHARE",
  "INTMEET", "INTLNLY", "INTRUST",
  "GENDTECH", "AGETECH", "CLASSTECH", "EDUCTECH",
  # Politics & civic engagement
  "POLINT", "LEFTRGHT1", "INTNEWS", "INTVIEWS"
)

# Standardise names to upper case (gssr sometimes ships lowercase)
names(gss_all) <- toupper(names(gss_all))

found    <- key_vars[key_vars %in% names(gss_all)]
missing  <- key_vars[!key_vars %in% names(gss_all)]
cat("Variables found :", length(found), "/", length(key_vars), "\n")
if (length(missing) > 0) cat("Missing vars    :", paste(missing, collapse = ", "), "\n")

# Define labels for the 3-category tech items
tech_labels <- c(
  GENDTECH  = "Tech favors men",
  AGETECH   = "Tech favors young",
  CLASSTECH = "Tech favors wealthy",
  EDUCTECH  = "Tech favors educated"
)

# ── 2. Recode demographics & build groups ────────────────────────────────────

df <- gss_all %>%
  # Strip haven labels → plain numeric (keeps value but drops label class)
  mutate(across(where(is.labelled), ~ as.numeric(.x))) %>%
  mutate(
    age      = AGE,
    male     = as.integer(SEX == 1),
    # Age band
    age_grp  = case_when(
      age >= 18 & age <= 29 ~ "18-29",
      age >= 30 & age <= 44 ~ "30-44",
      age >= 45 & age <= 64 ~ "45-64",
      age >= 65             ~ "65+",
      TRUE                  ~ NA_character_
    ),
    # Focal comparison group flags
    young_male  = as.integer(male == 1 & age_grp == "18-29"),
    young       = as.integer(age_grp == "18-29"),
    # Readable group label for every respondent
    group4 = case_when(
      male == 1 & age_grp == "18-29" ~ "Young Men (18-29)",
      male == 0 & age_grp == "18-29" ~ "Young Women (18-29)",
      male == 1                      ~ "Older Men (30+)",
      male == 0                      ~ "Older Women (30+)",
      TRUE                           ~ NA_character_
    )
  )

# ── 3. Handle reserved / missing codes ──────────────────────────────────────
#
# GSS convention: values like 0, -1, 8, 9, 98, 99 can mean IAP / DK / NA
# depending on the variable.  The code below sets common reserved codes to NA.
# Adjust if your extract already codes them as NA.

# For the 1-5 / 1-7 Likert items, values > 7 are reserved
likert_5  <- c("INTGAME","INTSTREAM","INTSHARE","INTMEET","INTLNLY",
               "POLINT","INTNEWS")
likert_7  <- c("INTRNETUSE")
likert_6  <- c("INTVIEWS")
scale_011 <- c("INTRUST","LEFTRGHT1")
cat_3     <- c("GENDTECH","AGETECH","CLASSTECH","EDUCTECH")

df <- df %>%
  mutate(
    across(all_of(likert_5),
           ~ ifelse(.x %in% 1:5, .x, NA_real_)),
    across(all_of(likert_7),
           ~ ifelse(.x %in% 1:7, .x, NA_real_)),
    across(all_of(likert_6),
           ~ ifelse(.x %in% 1:6, .x, NA_real_)),
    across(all_of(scale_011),
           ~ ifelse(.x %in% 0:10, .x, NA_real_)),
    across(all_of(cat_3),
           ~ ifelse(.x %in% 1:3, .x, NA_real_))
  )

# ── 3b. Reverse scales so HIGHER = MORE / STRONGER throughout ───────────────
#
# The GSS codes most items so that 1 = highest frequency / strongest agreement,
# which is counterintuitive for visualization (lower values on the right).
# We flip all reversed items so that higher values consistently mean
# "more frequent," "stronger agreement," or "more of the thing."
#
# Items that already go in the intuitive direction (INTRUST 0-10, LEFTRGHT1
# 0-10) are left as-is. Categorical items (GENDTECH etc.) are not flipped.

df <- df %>%
  mutate(
    # 1-5 items: flip so 5 = most frequent / strongest agreement
    across(all_of(likert_5), ~ 6 - .x),
    # INTRNETUSE (1-7): flip so 7 = almost all the time
    across(all_of(likert_7), ~ 8 - .x),
    # INTVIEWS (1-6): flip so 6 = every day
    across(all_of(likert_6), ~ 7 - .x)
    # INTRUST (0-10): already 10 = complete trust — no flip
    # LEFTRGHT1 (0-10): already 10 = right — no flip
  )

# ── 4. Choose weight ────────────────────────────────────────────────────────
#
# NORC recommends WTSSNRPS for 2024 cross-section analysis.
# Fall back to WTSSPS if the NR version isn't in the extract.

wt_var <- if ("WTSSNRPS" %in% names(df)) "WTSSNRPS" else "WTSSPS"
cat("Using weight:", wt_var, "\n")

df <- df %>%
  rename(wt = all_of(wt_var)) %>%
  filter(!is.na(wt), wt > 0)

# ── 5. Survey design object ────────────────────────────────────────────────

svy <- df %>%
  as_survey_design(weights = wt)

# ══════════════════════════════════════════════════════════════════════════════
#
#                 PART A — WEIGHTED DESCRIPTIVE COMPARISONS
#
# ══════════════════════════════════════════════════════════════════════════════

# ── 5a. Compute weighted means by group ──────────────────────────────────────

# We'll compute mean (treating ordinal as quasi-interval) ± SE for each
# variable x group.  For categorical 3-level items we compute proportions.

# Helper: weighted mean & SE for a single variable across the 4 groups
wmean_by_group <- function(svy_obj, varname) {
  svy_obj %>%
    filter(!is.na(.data[[varname]]), !is.na(group4)) %>%
    group_by(group4) %>%
    summarise(
      mean = survey_mean(.data[[varname]], na.rm = TRUE, vartype = "se")
    ) %>%
    mutate(variable = varname)
}

# Also compute an "All" group mean
wmean_all <- function(svy_obj, varname) {
  svy_obj %>%
    filter(!is.na(.data[[varname]])) %>%
    summarise(
      mean = survey_mean(.data[[varname]], na.rm = TRUE, vartype = "se")
    ) %>%
    mutate(variable = varname, group4 = "General Population")
}

# Run across all ordinal / scale variables
ordinal_vars <- c(
  "INTRNETUSE", "INTGAME", "INTSTREAM", "INTSHARE",
  "INTMEET", "INTLNLY", "INTRUST",
  "POLINT", "LEFTRGHT1", "INTNEWS", "INTVIEWS"
)

desc_group <- map_dfr(ordinal_vars, ~ wmean_by_group(svy, .x))
desc_all   <- map_dfr(ordinal_vars, ~ wmean_all(svy, .x))

desc <- bind_rows(desc_group, desc_all)

# Print a tidy summary table
desc_wide <- desc %>%
  select(variable, group4, mean) %>%
  pivot_wider(names_from = group4, values_from = mean) %>%
  arrange(variable)

cat("\n═══ Weighted group means (higher = more frequent / stronger agreement) ═══\n\n")
print(as.data.frame(desc_wide), digits = 2, row.names = FALSE)

# ── 5b. Proportion tables for 3-category tech-benefit items ─────────────────

prop_by_group <- function(svy_obj, varname) {
  svy_obj %>%
    filter(!is.na(.data[[varname]]), !is.na(group4)) %>%
    mutate(val = factor(.data[[varname]])) %>%
    group_by(group4, val) %>%
    summarise(prop = survey_mean(vartype = "se")) %>%
    mutate(variable = varname)
}

tech_props <- map_dfr(cat_3, ~ prop_by_group(svy, .x))

cat("\n═══ Weighted proportions for tech-benefit perceptions ═══\n\n")
tech_props %>%
  select(variable, group4, val, prop) %>%
  pivot_wider(names_from = val, values_from = prop) %>%
  arrange(variable, group4) %>%
  as.data.frame() %>%
  print(digits = 2, row.names = FALSE)


# ══════════════════════════════════════════════════════════════════════════════
#
#                       PART B — VISUALISATIONS
#
# ══════════════════════════════════════════════════════════════════════════════

# Global theme: Times New Roman, larger text throughout
theme_set(
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      panel.grid.minor = element_blank(),
      plot.title       = element_text(face = "bold", size = 18),
      plot.subtitle    = element_text(size = 13, colour = "grey40"),
      plot.caption     = element_text(size = 13),
      axis.text        = element_text(size = 13),
      axis.title       = element_text(size = 14),
      legend.text      = element_text(size = 13),
      strip.text       = element_text(face = "bold", size = 14)
    )
)

# Custom palette — Young Men highlighted
pal <- c(
  "Young Men (18-29)"   = "#E63946",
  "Young Women (18-29)" = "#457B9D",
  "Older Men (30+)"     = "#F4A261",
  "Older Women (30+)"   = "#2A9D8F",
  "General Population"  = "#6C757D"
)

# ── 6a. Dot plot of weighted means (ordinal items) ──────────────────────────

# Variable labels for readability (all variables — used by model plots too)
var_labels <- c(
  INTRNETUSE = "Internet use frequency (1-7)",
  INTGAME    = "Online gaming frequency",
  INTSTREAM  = "Streaming frequency",
  INTSHARE   = "Photo/video sharing",
  INTMEET    = "Comfortable meeting online",
  INTLNLY    = "Would feel lonely w/o internet",
  INTRUST    = "Trust people met online (0-10)",
  POLINT     = "Political interest",
  LEFTRGHT1  = "Left-right self-placement (0-10)",
  INTNEWS    = "Online news consumption",
  INTVIEWS   = "Discuss politics online (1-6)"
)

# ── Dot plot: only 1-5 scale items, two panels, alternating row shading ──────
# Panel 1: Men vs Women (ages 18-29 only) — isolates the gender effect
# Panel 2: Under 30 vs 30+ (all respondents) — isolates the age effect
#
# INTRUST (0-10), INTRNETUSE (7-point), LEFTRGHT1 (0-10), POLINT (political),
# and INTVIEWS (6-point) are excluded to keep the x-axis on one consistent
# scale.  These are reported in a separate summary table below.

dotplot_vars <- c("INTGAME", "INTSTREAM", "INTSHARE",
                  "INTMEET", "INTLNLY", "INTNEWS")

dotplot_labels <- var_labels[dotplot_vars]

scale_note <- "Higher = more frequent / stronger agreement (all items on 1\u20135 scale)"

# ── Panel 1 data: Men vs Women among 18-29 ─────────────────────────────────

panel1 <- desc %>%
  filter(variable %in% dotplot_vars,
         group4 %in% c("Young Men (18-29)", "Young Women (18-29)")) %>%
  mutate(
    label     = factor(var_labels[variable], levels = rev(dotplot_labels)),
    compare   = ifelse(grepl("Men", group4), "Young Men (18\u201329)", "Young Women (18\u201329)"),
    facet     = "Youth (18\u201329): Men vs. Women"
  )

# ── Panel 2 data: Young Men vs Older Men ──────────────────────────────────

panel2 <- desc %>%
  filter(variable %in% dotplot_vars,
         group4 %in% c("Young Men (18-29)", "Older Men (30+)")) %>%
  mutate(
    label     = factor(var_labels[variable], levels = rev(dotplot_labels)),
    compare   = ifelse(grepl("Young", group4), "Young Men (18\u201329)", "Older Men (30+)"),
    facet     = "Men only: Young vs. Older"
  )

# ── Combine ─────────────────────────────────────────────────────────────────

pal_panel <- c("Young Men (18\u201329)"  = "#E63946",
               "Young Women (18\u201329)" = "#457B9D",
               "Older Men (30+)"        = "#F4A261")

plot_combined <- bind_rows(panel1, panel2) %>%
  mutate(
    facet   = factor(facet, levels = c("Youth (18\u201329): Men vs. Women",
                                       "Men only: Young vs. Older")),
    compare = factor(compare, levels = names(pal_panel))
  )

# Alternating row backgrounds
n_rows <- length(dotplot_vars)
row_rects <- tibble(
  ymin  = seq(0.5, n_rows - 0.5, by = 1),
  ymax  = seq(1.5, n_rows + 0.5, by = 1),
  row_n = seq_along(seq_len(n_rows)),
  fill  = ifelse(row_n %% 2 == 0, "grey92", "grey98")
)

p_means <- ggplot(plot_combined, aes(x = mean, y = label, colour = compare)) +
  # Alternating row backgrounds
  geom_rect(data = row_rects, inherit.aes = FALSE,
            aes(xmin = -Inf, xmax = Inf, ymin = ymin, ymax = ymax, fill = fill)) +
  scale_fill_identity() +
  # Data — reverse = TRUE so first legend item is on top
  geom_point(size = 3.5, position = position_dodge(width = 0.5, reverse = TRUE)) +
  geom_errorbarh(
    aes(xmin = mean - 1.96 * mean_se, xmax = mean + 1.96 * mean_se),
    height = 0.25, position = position_dodge(width = 0.5, reverse = TRUE)
  ) +
  facet_wrap(~ facet, scales = "free_x") +
  scale_colour_manual(values = pal_panel, name = NULL) +
  labs(
    title    = "How Young Men (18-29) Compare: Digital Life & Online Attitudes",
    subtitle = scale_note,
    x = "Weighted mean (\u00B1 95% CI)", y = NULL,
    caption  = "Source: GSS 2024, ISSP Digital Societies module \u00B7 Weight: WTSSNRPS"
  ) +
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
  theme(
    legend.position    = "bottom",
    panel.grid.minor   = element_blank(),
    panel.grid.major.y = element_blank(),
    strip.text         = element_text(face = "bold", size = 16),
    plot.title         = element_text(face = "bold", size = 20),
    plot.subtitle      = element_text(size = 13, colour = "grey40"),
    axis.text.y        = element_text(size = 14)
  )

ggsave("01_means_dotplot.png", p_means, width = 13, height = 9, dpi = 300)
cat("\nSaved: 01_means_dotplot.png\n")


# ── Summary table for variables on non-standard scales ──────────────────────
# These are excluded from the dot plot to keep scales comparable, but their
# group means are reported here for completeness.

other_vars <- c("INTRUST", "INTRNETUSE", "POLINT", "LEFTRGHT1", "INTVIEWS")

cat("\n\u2550\u2550\u2550 Weighted means for variables on non-standard scales \u2550\u2550\u2550\n\n")
cat("  INTRUST:    0=No trust at all ... 10=Complete trust\n")
cat("  INTRNETUSE: 1=Never ... 7=Almost all the time (higher=more frequent)\n")
cat("  POLINT:     1=Not at all interested ... 5=Very interested (higher=more interested)\n")
cat("  LEFTRGHT1:  0=Left ... 10=Right (unchanged)\n")
cat("  INTVIEWS:   1=Never ... 6=Every day (higher=more frequent)\n\n")

desc %>%
  filter(variable %in% other_vars) %>%
  select(variable, group4, mean) %>%
  pivot_wider(names_from = group4, values_from = mean) %>%
  arrange(match(variable, other_vars)) %>%
  as.data.frame() %>%
  print(digits = 2, row.names = FALSE)

write_csv(
  desc %>% filter(variable %in% other_vars),
  "table_other_scale_means.csv"
)
cat("\nSaved: table_other_scale_means.csv\n")


# ── 6b. Figure 02: Dot plots for non-standard-scale variables ────────────────
#
# Four variables excluded from Figure 01 because they're on different scales.
# Each gets its own small panel with a free x-axis so we can zoom in.

library(patchwork)

extra_vars <- c("INTRUST", "INTRNETUSE")

extra_titles <- c(
  INTRUST    = "Trust people met online (0\u201310, higher = more trust)",
  INTRNETUSE = "Internet use frequency (1\u20137, higher = more frequent)"
)

# Use the same 4-group palette as the main analysis
pal_4 <- c(
  "Young Men (18-29)"   = "#E63946",
  "Young Women (18-29)" = "#457B9D",
  "Older Men (30+)"     = "#F4A261",
  "Older Women (30+)"   = "#2A9D8F"
)

plot_extra_var <- function(varname) {
  
  d <- desc %>%
    filter(variable == varname,
           group4 != "General Population") %>%
    mutate(
      group4 = factor(group4, levels = rev(names(pal_4)))
    )
  
  ggplot(d, aes(x = mean, y = group4, colour = group4)) +
    geom_point(size = 3.5) +
    geom_errorbarh(
      aes(xmin = mean - 1.96 * mean_se, xmax = mean + 1.96 * mean_se),
      height = 0.3
    ) +
    scale_colour_manual(values = pal_4, guide = "none") +
    labs(title = extra_titles[varname], x = NULL, y = NULL) +
    theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      panel.grid.minor   = element_blank(),
      panel.grid.major.y = element_blank(),
      plot.title         = element_text(face = "bold", size = 14),
      axis.text.y        = element_text(size = 13)
    )
}

p_extra_list <- map(extra_vars, plot_extra_var)

p_fig02 <- (p_extra_list[[1]] / p_extra_list[[2]]) +
  plot_annotation(
    title   = "Additional Measures: Online Trust & Internet Use",
    caption = "Source: GSS 2024, ISSP Digital Societies module \u00B7 Weight: WTSSNRPS",
    theme   = theme(
      plot.title = element_text(face = "bold", size = 20)
    )
  )

ggsave("02_extra_dotplots.png", p_fig02, width = 9, height = 5, dpi = 300)
cat("Saved: 02_extra_dotplots.png\n")


# ══════════════════════════════════════════════════════════════════════════════
#
#         PART C — PREDICTIVE MODEL: What Predicts Being a Young Man?
#
# ══════════════════════════════════════════════════════════════════════════════
#
# Logistic regression: DV = young_male (1/0)
# IVs = all the digital-life and politics variables
# This tells us which attitudes most sharply distinguish young men from
# everyone else, net of each other.

# ── Diagnose missingness before modelling ────────────────────────────────────
#
# The ISSP module was given to a sub-sample (~1,500 Rs).  Requiring complete
# cases on ALL 15 predictors at once can shrink N drastically and leave zero
# young men in the analytic sample.  We check first, then adapt.

all_predictors <- c(ordinal_vars, cat_3)

cat("\n── Per-variable valid N and young-male counts ──\n")
for (v in all_predictors) {
  valid   <- df %>% filter(!is.na(.data[[v]]))
  n_ym    <- sum(valid$young_male, na.rm = TRUE)
  cat(sprintf("  %-12s  N = %4d   young men = %3d\n", v, nrow(valid), n_ym))
}

# Check full complete-case set
model_vars <- c("young_male", all_predictors)
df_full_cc <- df %>% select(all_of(model_vars), wt) %>% drop_na()
cat(sprintf("\nFull listwise-complete N = %d, young men = %d\n",
            nrow(df_full_cc), sum(df_full_cc$young_male)))

# ── Strategy: split into two domain-specific models if full model fails ─────
#
# Model A: Digital Life  (INTRNETUSE … EDUCTECH)  — 15 vars may be too many
# Model B: Politics      (POLINT, LEFTRGHT1, INTNEWS, INTVIEWS)
#
# We attempt the full model first; if it fails we fall back to domain models.

digital_vars  <- c("INTRNETUSE","INTGAME","INTSTREAM","INTSHARE",
                   "INTMEET","INTLNLY","INTRUST",
                   "GENDTECH","AGETECH","CLASSTECH","EDUCTECH")
politics_vars <- c("POLINT","LEFTRGHT1","INTNEWS","INTVIEWS")

fit_logit_safely <- function(predictors, label) {
  
  mod_vars <- c("young_male", predictors)
  d <- df %>% select(all_of(mod_vars), wt) %>% drop_na()
  
  n_ym <- sum(d$young_male)
  cat(sprintf("\n[%s] Complete cases: N = %d, young men = %d\n",
              label, nrow(d), n_ym))
  
  if (nrow(d) < 50 || n_ym < 10) {
    cat("  ⚠ Too few young men for stable estimation — skipping.\n")
    return(NULL)
  }
  
  svy_m <- svydesign(ids = ~1, weights = ~wt, data = d)
  fml   <- as.formula(paste("young_male ~", paste(predictors, collapse = " + ")))
  
  fit <- tryCatch(
    svyglm(fml, design = svy_m, family = quasibinomial()),
    error = function(e) { cat("  ⚠ Model error:", e$message, "\n"); NULL }
  )
  return(fit)
}

# Try full model first
fit_full <- fit_logit_safely(all_predictors, "Full model")

# If full model failed, run BOTH domain sub-models and combine
if (is.null(fit_full)) {
  cat("\nFull model did not converge — fitting domain sub-models.\n")
  fit_digital  <- fit_logit_safely(digital_vars,  "Digital Life")
  fit_politics <- fit_logit_safely(politics_vars, "Politics")
  
  # Collect ALL that succeeded — both domains appear in the forest plot
  fits <- list("Digital Life" = fit_digital, "Politics" = fit_politics)
  fits <- compact(fits)   # drop NULLs
} else {
  fits <- list("Full model" = fit_full)
}

# ── Print summaries & build tidy table ──────────────────────────────────────
tidy_logit <- map_dfr(names(fits), function(nm) {
  cat(sprintf("\n═══ Logistic Regression [%s]: Predicting Young Male 18-29 ═══\n\n", nm))
  print(summary(fits[[nm]]))
  
  tidy(fits[[nm]], conf.int = TRUE, exponentiate = TRUE) %>%
    filter(term != "(Intercept)") %>%
    mutate(model = nm)
}) %>%
  mutate(
    term_label = case_when(
      term %in% names(var_labels)  ~ var_labels[term],
      term %in% names(tech_labels) ~ tech_labels[term],
      TRUE ~ term
    ),
    sig = ifelse(p.value < 0.05, "p < .05", "n.s.")
  )

# ── 6c. Forest plot of odds ratios ──────────────────────────────────────────

if (nrow(tidy_logit) > 0) {
  
  p_forest <- tidy_logit %>%
    ggplot(aes(x = estimate, y = reorder(term_label, estimate),
               colour = sig)) +
    geom_vline(xintercept = 1, linetype = "dashed", colour = "grey50") +
    geom_point(size = 3) +
    geom_errorbarh(aes(xmin = conf.low, xmax = conf.high), height = 0.25) +
    scale_colour_manual(values = c("p < .05" = "#E63946", "n.s." = "grey60"),
                        name = NULL) +
    # If we had to split into sub-models, facet them
    { if (n_distinct(tidy_logit$model) > 1)
      facet_wrap(~ model, scales = "free_y", ncol = 1) } +
    labs(
      title = "What Attitudes Predict Being a Young Man (18-29)?",
      subtitle = "Odds ratios from weighted logistic regression",
      x = "Odds Ratio (95% CI)", y = NULL,
      caption = "Source: GSS 2024, ISSP Digital Societies module · Weight: WTSSNRPS"
    ) +
    theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      legend.position = "bottom",
      plot.title = element_text(face = "bold")
    )
  
  ggsave("03_forest_odds_ratios.png", p_forest, width = 10, height = 7, dpi = 300)
  cat("Saved: 03_forest_odds_ratios.png\n")
  
} else {
  cat("\n⚠ No logistic models converged. Cell sizes may be too small.\n",
      "  Consider collapsing age bands (e.g., 18-34) or reducing predictors.\n")
}


# ══════════════════════════════════════════════════════════════════════════════
#
#      PART D — SUPPLEMENTARY: Ordinal Models for Key Outcomes
#
# ══════════════════════════════════════════════════════════════════════════════
#
# Instead of predicting group membership, we can also ask:
# "Does being a young man predict each attitude, controlling for demographics?"
#
# Here we run survey-weighted OLS (treating ordinal as quasi-interval)
# for each DV with young_male as the key predictor, controlling for age and sex
# main effects so the interaction (young + male) is isolated.

cat("\n═══ Outcome-Level Models: Effect of Young Male on Each Attitude ═══\n\n")

outcome_models <- map_dfr(c(ordinal_vars, cat_3), function(v) {
  
  tmp <- df %>%
    select(all_of(v), young_male, male, age, wt) %>%
    drop_na()
  
  svy_tmp <- svydesign(ids = ~1, weights = ~wt, data = tmp)
  
  f <- as.formula(paste(v, "~ young_male + male + age"))
  
  m <- tryCatch(
    svyglm(f, design = svy_tmp, family = gaussian()),
    error = function(e) NULL
  )
  
  if (is.null(m)) return(tibble())
  
  tidy(m, conf.int = TRUE) %>%
    filter(term == "young_male") %>%
    mutate(outcome = v)
})

outcome_summary <- outcome_models %>%
  mutate(
    outcome_label = coalesce(var_labels[outcome], tech_labels[outcome], outcome),
    sig = ifelse(p.value < 0.05, "*", "")
  ) %>%
  select(outcome_label, estimate, std.error, conf.low, conf.high, p.value, sig)

print(as.data.frame(outcome_summary), digits = 3, row.names = FALSE)

# ── 6d. Coefficient plot for young-male effect across outcomes ──────────────

p_outcome <- outcome_models %>%
  mutate(
    outcome_label = coalesce(var_labels[outcome], tech_labels[outcome], outcome),
    sig = ifelse(p.value < 0.05, "p < .05", "n.s.")
  ) %>%
  ggplot(aes(x = estimate, y = reorder(outcome_label, estimate), colour = sig)) +
  geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +
  geom_point(size = 3) +
  geom_errorbarh(aes(xmin = conf.low, xmax = conf.high), height = 0.25) +
  scale_colour_manual(values = c("p < .05" = "#E63946", "n.s." = "grey60"),
                      name = NULL) +
  labs(
    title = "The 'Young Male' Effect on Each Attitude",
    subtitle = paste0(
      "Coefficients from survey-weighted OLS, controlling for sex and age\n",
      "Positive = young men score higher (more frequent / stronger agreement on most scales)"
    ),
    x = "Coefficient for Young Male (18-29) indicator", y = NULL,
    caption = "Source: GSS 2024, ISSP Digital Societies module · Weight: WTSSNRPS"
  ) +
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
  theme(
    legend.position = "bottom",
    plot.title = element_text(face = "bold")
  )

ggsave("04_young_male_effects.png", p_outcome, width = 10, height = 7, dpi = 300)
cat("Saved: 04_young_male_effects.png\n")


# ══════════════════════════════════════════════════════════════════════════════
#
#                       PART E — EXPORT RESULTS TABLE
#
# ══════════════════════════════════════════════════════════════════════════════

cat("\n═══ Writing results to CSV ═══\n")

write_csv(desc_wide, "table_weighted_means.csv")
write_csv(
  tech_props %>% select(variable, group4, val, prop, prop_se),
  "table_tech_proportions.csv"
)
write_csv(tidy_logit, "table_logit_odds_ratios.csv")
write_csv(outcome_summary, "table_young_male_effects.csv")

cat("Done. Four CSVs and four PNGs saved to working directory.\n")

# ══════════════════════════════════════════════════════════════════════════════
#
#                       NOTES FOR THE THESIS
#
# ══════════════════════════════════════════════════════════════════════════════
#
# 1. WEIGHT:
#    WTSSNRPS is the NORC-recommended post-stratification weight for the
#    2024 GSS cross-section. It adjusts for probability of selection,
#    non-response, and rakes to known population totals.
#
# 2. ISSP MODULE AVAILABILITY:
#    The "Digital Societies" module is BRAND NEW in 2024 (first replication).
#    These variables do NOT exist in earlier GSS waves.  You cannot track
#    trends over time with them.  For trend analysis, use core GSS items
#    that recur across waves (e.g., PARTYID, POLVIEWS, HAPPY, etc.).
#
# 3. SCALE DIRECTION (after reversal — higher = more throughout):
#    - INTRNETUSE: 1 = never … 7 = almost all the time
#    - INTGAME/INTSTREAM/INTSHARE/INTNEWS: 1 = never … 5 = very often
#    - INTMEET/INTLNLY: 1 = strongly disagree … 5 = strongly agree
#    - INTVIEWS: 1 = never … 6 = every day
#    - POLINT: 1 = not at all interested … 5 = very interested
#    - INTRUST: 0 = no trust … 10 = complete trust (unchanged)
#    - LEFTRGHT1: 0 = left … 10 = right (unchanged)
#    - GENDTECH/AGETECH/CLASSTECH/EDUCTECH: 1/2/3 categorical (unchanged)
#
# 4. SAMPLE SIZE:
#    The 2024 GSS cross-section has ~3,309 cases.  The ISSP module was
#    administered to a sub-sample (~1,500–1,600 respondents).  The young
#    men 18-29 cell will be relatively small — expect wide CIs.  Report
#    cell sizes alongside estimates.
#
# 5. FURTHER EXTENSIONS:
#    - If you want to test interaction effects (e.g., age × sex on each
#      outcome), add interaction terms to the Part D models.
#    - For truly ordinal treatment, swap svyglm(..., gaussian()) for
#      svyolr() from the svyVGAM package or use MASS::polr() on the
#      unweighted data with robust SEs.
#    - Consider adding RACE, EDUC, INCOME as controls in Part C/D.
################################################################################