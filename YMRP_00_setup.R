# =============================================================================
# YMRP_00_setup.R
# Master setup file: loads data, applies weights, recodes all variables.
# All other YMRP scripts source() this file at the top.
# =============================================================================

library(tidyverse)
library(survey)      # For svydesign() and weighted models
library(psych)       # For alpha() and principal()
library(jtools)      # For theme_nice()
library(marginaleffects)
library(MASS)        # For polr()
library(gtsummary)
library(gt)

# -----------------------------------------------------------------------------
# 1. LOAD DATA
# -----------------------------------------------------------------------------
dat <- read_csv("YMRI_202505.csv")

# -----------------------------------------------------------------------------
# 2. DEFINE CREATOR INDICES
# These are the indices x in trust_grid_x / familiarity_grid_x that correspond
# to the Trump-endorsing "manosphere" creators.
# -----------------------------------------------------------------------------
creator_indices <- c(1, 2, 3, 4, 5, 10, 11, 16, 18, 19, 24)
trust_cols        <- paste0("trust_grid_",       creator_indices)
familiarity_cols  <- paste0("familiarity_grid_", creator_indices)

# -----------------------------------------------------------------------------
# 3. RECODE HELPERS
# Survey scale: 1 = Strongly Agree, 2 = Somewhat Agree, 5 = Not Sure,
#               3 = Somewhat Disagree, 4 = Strongly Disagree
# recode_standard: 1→5 (Strongly Agree = High)
# recode_reverse:  1→1 (Strongly Agree = Low, used for reverse-coded items)
# -----------------------------------------------------------------------------
recode_standard <- function(x) {
  case_when(x == 1 ~ 5, x == 2 ~ 4, x == 5 ~ 3, x == 3 ~ 2, x == 4 ~ 1,
            TRUE ~ NA_real_)
}
recode_reverse <- function(x) {
  case_when(x == 1 ~ 1, x == 2 ~ 2, x == 5 ~ 3, x == 3 ~ 4, x == 4 ~ 5,
            TRUE ~ NA_real_)
}

# -----------------------------------------------------------------------------
# 4. SEXISM BATTERY (s1–s11)
# Items (all recoded so Higher = More Sexist):
#   s1  = sexism_battery_1  – standard  (guys can't speak minds)
#   s2  = sexism_battery_2  – standard  (society looks down on masculine men)
#   s3  = sexism_battery_3  – standard  (men breadwinner / women home)
#   s4  = sexism_battery_4  – REVERSE   (women should hold more power / men do more housework)
#   s5  = sexism_battery_5  – standard  (feminism favors women over men)
#   s6  = sexism_battery_6  – standard  (men should be valued more in society)
#   s7  = sexism_battery_7  – REVERSE   (media is biased towards men — agreeing = less sexist)
#   s8  = sexism_battery_8  – standard  (roles only men can do)
#   s9  = sexism_battery_9  – standard  (roles only women can do)
#   s10 = sexism_battery_10 – standard  (gay men aren't really men)
#   s11 = sexism_battery_11 – standard  (trans men aren't really men)
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    s1  = recode_standard(sexism_battery_1),
    s2  = recode_standard(sexism_battery_2),
    s3  = recode_standard(sexism_battery_3),
    s4  = recode_reverse(sexism_battery_4),
    s5  = recode_standard(sexism_battery_5),
    s6  = recode_standard(sexism_battery_6),
    s7  = recode_reverse(sexism_battery_7),
    s8  = recode_standard(sexism_battery_8),
    s9  = recode_standard(sexism_battery_9),
    s10 = recode_standard(sexism_battery_10),
    s11 = recode_standard(sexism_battery_11),
    sexism_index = rowMeans(across(s1:s11), na.rm = TRUE)
  )

# -----------------------------------------------------------------------------
# 5. RACISM BATTERY (r1–r3)
# r1 = racism_battery_1 – REVERSE (agreeing = aware of white privilege = low racism)
# r2 = racism_battery_2 – standard (racism is rare)
# r3 = racism_battery_3 – standard (society provokes / reverse racism grievance)
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    r1 = recode_reverse(racism_battery_1),
    r2 = recode_standard(racism_battery_2),
    r3 = recode_standard(racism_battery_3)
  )

# -----------------------------------------------------------------------------
# 6. CREATOR TRUST / FAMILIARITY VARIABLES
# trust_grid_x:       1 = Trust, 2 = Follow but skeptical, 3+ = not a fan / unfamiliar
# familiarity_grid_x: indicates recognition level
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    # Number of creators actively trusted (answered 1 = Trust)
    n_trusted = rowSums(across(all_of(trust_cols),  ~ .x == 1), na.rm = TRUE),
    # Number of creators recognized (familiar or following, regardless of trust)
    n_recognized = rowSums(across(all_of(familiarity_cols), ~ .x %in% c(1, 2)), na.rm = TRUE),
    # Number of creators followed
    n_following = rowSums(across(all_of(trust_cols), ~ .x == 2), na.rm = TRUE),
    n_following_only = rowSums(
      across(all_of(trust_cols), ~ .x == 2) &   # follows/skeptical
        across(all_of(trust_cols), ~ .x != 1),    # but does NOT trust
      na.rm = TRUE
    ),
    
    # Categorical trust bucket
    trust_level = factor(
      case_when(
        n_trusted == 0 ~ "0",
        n_trusted == 1 ~ "1",
        n_trusted == 2 ~ "2",
        n_trusted >= 3 ~ "3+"
      ),
      levels = c("0", "1", "2", "3+")
    ),
    
    # Binary: trusts at least one creator
    # Stored as a factor with "Non-Truster" as the reference level
    is_truster_binary = factor(
      if_else(n_trusted > 0, "Truster", "Non-Truster"),
      levels = c("Non-Truster", "Truster")
    ),
    
    # 3-way fan hierarchy for ordered logit
    fan_status = factor(
      case_when(
        rowSums(across(all_of(trust_cols), ~ .x == 1), na.rm = TRUE) > 0 ~ "True Believer",
        rowSums(across(all_of(trust_cols), ~ .x == 2), na.rm = TRUE) > 0 ~ "Skeptical Fan",
        TRUE ~ "Non-Fan"
      ),
      levels = c("Non-Fan", "Skeptical Fan", "True Believer")
    ),
    
    is_true_believer = if_else(fan_status == "True Believer", 1L, 0L)
  )

# -----------------------------------------------------------------------------
# 7. DATING / LONELINESS VARIABLES
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    recent_breakup       = if_else(breakup %in% c(2, 3), 1L, 0L),
    never_relationship   = if_else(types_of_relationships == 1, 1L, 0L),
    past_relationship    = if_else(types_of_relationships == 2, 1L, 0L),
    active_relationship  = if_else(types_of_relationships == 4, 1L, 0L),
    # Loneliness: "I often feel lonely" (life_goals_14, recoded so 5 = strongly agree)
    loneliness           = recode_standard(life_goals_14),
    # Relationship grievance items (recoded so 5 = High Grievance)
    hard_to_meet         = recode_standard(relationship_experience_5),
    women_expectations   = recode_standard(relationship_experience_6)
  )

# -----------------------------------------------------------------------------
# 8. RACE LABELS
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    race_label = case_when(
      race4 == 1 ~ "White",
      race4 == 2 ~ "Black",
      race4 == 3 ~ "Hispanic",
      race4 == 4 ~ "Other/Multiracial",
      TRUE ~ NA_character_
    )
  )

# -----------------------------------------------------------------------------
# 9. VOTING OUTCOME VARIABLES
#
# Age eligibility: 2024 Election Day = November 5, 2024.
# Anyone born after Nov 5, 2006 was under 18 and ineligible.
# Since birthyr only gives year (not month/day), we use birthyr > 2006 as the
# cutoff. This is conservative: a handful born late 2006 may have been eligible,
# but given mean birthyr ~1999.89 this affects very few cases.
#
# Skipped codes (8, 98) -> NA throughout; we never treat skips as "no".
#
# Three outcome variables:
#
#   vote_trump_24         Among 2024 voters: 1 = Trump, 0 = voted someone else
#
#   vote_switch_to_trump  Among 2024 Trump voters only:
#                         1 = switcher (non-Trump or nonvoter in 2020)
#                         0 = loyalist (Trump in 2020 too)
#
#   vote_trump_new_24     Among all 2024 voters:
#                         1 = "new" Trump voter (switched OR newly mobilized)
#                         0 = did not vote Trump in 2024
#                         Best variable for the mobilization argument.
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    
    # Age eligibility flag
    eligible_2024 = (birthyr <= 2006),
    
    # Clean raw variables: skipped/out-of-range -> NA
    turnout20  = if_else(turnout20post  %in% c(1, 2), turnout20post,  NA_real_),
    vote20     = if_else(presvote20post %in% 1:6,     presvote20post, NA_real_),
    turnout24  = if_else(turnout24post  %in% c(1, 2), turnout24post,  NA_real_),
    vote24     = if_else(presvote24post %in% c(1:9),  presvote24post, NA_real_),
    
    # OUTCOME 1: Voted Trump in 2024
    # Denominator: eligible respondents who turned out in 2024.
    vote_trump_24 = case_when(
      !eligible_2024        ~ NA_integer_,
      turnout24 != 1        ~ NA_integer_,
      vote24 == 2           ~ 1L,
      vote24 %in% c(1,3:9) ~ 0L,
      TRUE                  ~ NA_integer_
    ),
    
    # OUTCOME 2: Switcher vs. Loyalist (among 2024 Trump voters only)
    # Use to model what differentiates switchers from loyalists.
    vote_switch_to_trump = case_when(
      vote_trump_24 != 1         ~ NA_integer_,
      vote20 == 2                ~ 0L,           # loyalist
      vote20 %in% c(1, 3:6)     ~ 1L,           # switched from other party
      turnout20 == 2             ~ 1L,           # sat out 2020, mobilized 2024
      TRUE                       ~ NA_integer_
    ),
    
    # OUTCOME 3: New Trump voter among all 2024 voters
    # Captures both party-switchers and newly mobilized nonvoters.
    vote_trump_new_24 = case_when(
      !eligible_2024             ~ NA_integer_,
      turnout24 != 1             ~ NA_integer_,
      vote24 != 2                ~ 0L,           # voted but not Trump
      vote20 == 2                ~ 0L,           # loyal Trump voter, not new
      vote20 %in% c(1, 3:6)     ~ 1L,           # switched from another 2020 candidate
      turnout20 == 2             ~ 1L,           # sat out 2020, voting Trump for first time
      TRUE                       ~ NA_integer_
    )
  )

cat("\n--- Voting Outcome Sanity Check ---\n")
cat("Ineligible (born after 2006):     ", sum(!dat$eligible_2024, na.rm = TRUE), "\n")
cat("vote_trump_24:        1 =", sum(dat$vote_trump_24 == 1, na.rm=TRUE),
    " 0 =", sum(dat$vote_trump_24 == 0, na.rm=TRUE),
    " NA =", sum(is.na(dat$vote_trump_24)), "\n")
cat("vote_switch_to_trump: 1 =", sum(dat$vote_switch_to_trump == 1, na.rm=TRUE),
    " 0 =", sum(dat$vote_switch_to_trump == 0, na.rm=TRUE),
    " NA =", sum(is.na(dat$vote_switch_to_trump)), "\n")
cat("vote_trump_new_24:    1 =", sum(dat$vote_trump_new_24 == 1, na.rm=TRUE),
    " 0 =", sum(dat$vote_trump_new_24 == 0, na.rm=TRUE),
    " NA =", sum(is.na(dat$vote_trump_new_24)), "\n")

# -----------------------------------------------------------------------------
# 10. ADDITIONAL CONTROL VARIABLES
#
# pid7_with_leaners: 1 = Dem/Lean Dem, 2 = Rep/Lean Rep, 3 = Pure Ind
#   Collapses the original 7-point PID into a 3-category variable.
#   Coded as ordered factor so it enters models as a meaningful numeric control.
#
# urbancity3: 1 = Urban, 2 = Suburban, 3 = Rural
#   Collapses original urbancity variable (which may have more categories).
#
# age5: Age in 5 groups. Derived from birthyr against a fixed reference of 2024.
#   1 = 18-24, 2 = 25-34, 3 = 35-44, 4 = 45-64, 5 = 65+
#
# NOTE: These join the existing controls (faminc5, race2, educ4).
# All models in files 02 and 03 should be updated to include these.
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    
    # Party ID factor
    # pid7_with_leaners is already 3-category: 1 = Dem, 2 = Rep, 3 = Ind
    # Convert to factor for use in models (see note below on factor treatment)
    pid3_factor = factor(
      pid7_with_leaners,
      levels = 1:3,
      labels = c("Democrat", "Republican", "Independent")
    ),
    
    # Age groups from birthyr (reference year = 2024)
    # Sample is 18-29, so standard adult age bins would collapse nearly everyone
    # into one category. Use four narrower bands within the range instead.
    #   1 = 18-20  (earliest eligible voters)
    #   2 = 21-23  (college-age)
    #   3 = 24-26  (early post-college)
    #   4 = 27-29  (late 20s)
    age_2024 = 2024 - birthyr,
    age4 = case_when(
      age_2024 %in% 18:20 ~ 1L,
      age_2024 %in% 21:23 ~ 2L,
      age_2024 %in% 24:26 ~ 3L,
      age_2024 %in% 27:29 ~ 4L,
      TRUE                ~ NA_integer_
    )
  )

cat("pid7_with_leaners distribution:\n"); print(table(dat$pid7_with_leaners, useNA = "always"))
cat("urbancity3 distribution:\n"); print(table(dat$urbancity3, useNA = "always"))
cat("age4 distribution:\n"); print(table(dat$age4, useNA = "always"))

# -----------------------------------------------------------------------------
# 11. SOCIAL MEDIA VARIABLES
#
# Two sets of variables:
#   A. socialmediause_ymri_1:23  — which platforms used in past week (1=yes,2=no)
#   B. platform_use_*            — hours per week on each platform (1-4 = hours,
#                                  5 = don't use)
#
# Derived variables created here:
#   n_platforms_used   Count of platforms used in past week (any = selected)
#   alt_platform_user  1 = used any "manosphere-adjacent" platform in past week
#                      (4chan, Gab, Parler, Rumble, Telegram)
#   right_platform_user 1 = used X or any alt-right platform
#   hrs_youtube / hrs_x / hrs_tiktok / hrs_reddit
#                      Numeric hours from platform_use_* (5 = don't use → 0)
#   total_social_hrs   Sum of hours across all measured platforms
# -----------------------------------------------------------------------------

# Platforms used in past week (1 = selected, 2 = not selected → recode to 0/1)
smu_vars <- paste0("socialmediause_ymri_", 1:22)   # _23 is "none of the above"

dat <- dat |>
  mutate(
    across(all_of(smu_vars), ~ if_else(. == 1, 1L, 0L, missing = 0L),
           .names = "{.col}_bin"),
    
    # Count of platforms used
    n_platforms_used = rowSums(across(paste0(smu_vars, "_bin")), na.rm = TRUE),
    
    # Manosphere-adjacent platforms (4chan=1, Gab=4, Parler=8, Rumble=11, Telegram=14)
    alt_platform_user = if_else(
      socialmediause_ymri_1_bin  == 1 |   # 4chan
        socialmediause_ymri_4_bin  == 1 |   # Gab
        socialmediause_ymri_8_bin  == 1 |   # Parler
        socialmediause_ymri_11_bin == 1 |   # Rumble
        socialmediause_ymri_14_bin == 1,    # Telegram
      1L, 0L
    ),
    
    # Right-coded platforms: X + alt platforms
    right_platform_user = if_else(
      alt_platform_user == 1 |
        socialmediause_ymri_19_bin == 1,    # X / Twitter
      1L, 0L
    )
  )

# Hours on each platform: recode 5 (don't use) → 0, keep 1-4 as ordinal hours
# 1 = <1hr, 2 = 2-3hrs, 3 = 3-4hrs, 4 = 4+hrs per day
recode_hrs <- function(x) if_else(x == 5, 0L, as.integer(x), missing = NA_integer_)

dat <- dat |>
  mutate(
    hrs_youtube  = recode_hrs(platform_use_youtube),
    hrs_x        = recode_hrs(platform_use_x),
    hrs_tiktok   = recode_hrs(platform_use_tiktok),
    hrs_reddit   = recode_hrs(platform_use_reddit),
    hrs_rumble   = recode_hrs(platform_use_rumble),
    hrs_discord  = recode_hrs(platform_use_discord),
    hrs_instagram = recode_hrs(platform_use_insta),
    hrs_facebook  = recode_hrs(platform_use_facebook),
    total_social_hrs = rowSums(
      across(starts_with("hrs_")), na.rm = TRUE
    )
  )

cat("Alt platform users:", sum(dat$alt_platform_user, na.rm = TRUE), "\n")
cat("Right platform users:", sum(dat$right_platform_user, na.rm = TRUE), "\n")
cat("Mean platforms used:", round(mean(dat$n_platforms_used, na.rm = TRUE), 2), "\n")

# -----------------------------------------------------------------------------
# 12. FACTOR CATEGORICAL CONTROLS
# pid7_with_leaners and urbancity3 are nominal/unordered categories.
# Factor them so they enter models as dummy indicators, not as continuous.
# faminc5, educ4, race2 are ordinal or binary and can remain numeric.
# -----------------------------------------------------------------------------
dat <- dat |>
  mutate(
    pid7_with_leaners = factor(pid7_with_leaners,
                               levels = 1:3,
                               labels = c("Democrat", "Republican", "Independent")),
    urbancity3 = factor(urbancity3,
                        levels = 1:3,
                        labels = c("Urban", "Suburban", "Rural"))
  )

# -----------------------------------------------------------------------------
# 13. SURVEY DESIGN OBJECT
# Built AFTER all variable creation so every column is available to svyglm().
# YouGov opt-in panel: weight post-stratifies for age, race, gender, education.
# ids = ~1 because no cluster/PSU variable is available.
# -----------------------------------------------------------------------------
svy <- svydesign(
  ids     = ~1,
  weights = ~weight,
  data    = dat
)

# ── Global theme (mirrors GSS file exactly) ──────────────────────────────────
theme_set(
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      panel.grid.minor = element_blank(),
      plot.title       = element_text(face = "bold", size = 18),
      plot.subtitle    = element_text(size = 13, colour = "grey40"),
      plot.caption     = element_text(size = 12),
      axis.text        = element_text(size = 13),
      axis.text.x      = element_text(size = 13, margin = margin(t = 4)),
      axis.title       = element_text(size = 14),
      legend.text      = element_text(size = 13),
      strip.text       = element_text(face = "bold", size = 14),
      legend.position  = "bottom",
      plot.margin      = margin(t = 5, r = 10, b = 5, l = 5, unit = "pt")
    )
)


cat("
=== YMRP Setup Complete ===
Observations:    ", nrow(dat), "
Creators tracked:", length(creator_indices), "(indices:", paste(creator_indices, collapse=", "), ")
Trust columns:   ", paste(trust_cols, collapse=", "), "
Sexism index:    mean =", round(mean(dat$sexism_index, na.rm=TRUE), 3),
    "| range =", round(min(dat$sexism_index, na.rm=TRUE),2), "–", round(max(dat$sexism_index, na.rm=TRUE),2), "
Survey design:   svydesign object 'svy' created with weight column
\n")