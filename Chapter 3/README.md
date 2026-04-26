# Survey Analysis of the Attitudes and Opinions of Young Men

<br>

## General Social Survey (GSS) Analysis

Replication code for a study of young men's digital habits, political attitudes, and social wellbeing using the General Social Survey. Covers a cross-sectional analysis of the 2024 ISSP "Digital Societies" module and a longitudinal trend analysis spanning 1972–2024.

---

### Data

This repository contains only the analysis code. The raw data required to replicate consists of:

```
data/
    GSS2024.dta               # 2024 GSS cross-section (ISSP Digital Societies module)
    GSS7224_R1.dta            # GSS cumulative file, 1972–2024
```

Both files are available from the **GSS Data Explorer** at [gssdataexplorer.norc.org](https://gssdataexplorer.norc.org). A free account is required. Download in Stata (`.dta`) format for compatibility with this code.

---

### Setup

```r
install.packages(c(
  "haven",      # read Stata .dta files
  "survey",     # survey-weighted analysis
  "srvyr",      # tidy wrappers for survey package
  "tidyverse",  # data wrangling and ggplot2
  "labelled",   # handle haven-labelled columns
  "scales",     # axis formatting
  "patchwork"   # combine ggplot panels
))
```

R 4.1+ required. Times New Roman must be installed on your system for plot fonts to render correctly. On Mac, if fonts do not load, run:

```r
install.packages("extrafont")
library(extrafont)
font_import()
```

---

### Files

#### `01_gss_young_men_analysis.R`: GSS Cross-Sectional Analysis

Cross-sectional analysis of the 2024 GSS ISSP Digital Societies module. Requires `GSS2024.dta`.

**Outputs:**

```
01_means_dotplot.png              # Fig. 01 — Two-panel dot plot: digital behaviors
                                  #   Left: Young Men vs. Young Women (18-29)
                                  #   Right: Young Men vs. Older Men (30+)
02_extra_dotplots.png             # Fig. 02 — Dot plots for non-standard-scale variables
                                  #   INTRUST (0-10) and INTRNETUSE (1-7)
03_forest_odds_ratios.png         # Fig. 03 — Forest plot: ORs predicting Young Male membership
                                  #   (Weighted logistic regression, quasibinomial)
04_young_male_effects.png         # Fig. 04 — Coefficient plot: Young Male effect on each attitude
                                  #   (Survey-weighted OLS, controlling for sex and age)
table_weighted_means.csv          # Weighted group means — 1-5 scale items
table_other_scale_means.csv       # Weighted group means — non-standard scales
table_tech_proportions.csv        # Weighted proportions — tech-benefit perception items
table_logit_odds_ratios.csv       # Logistic regression coefficients and ORs
table_young_male_effects.csv      # OLS young male effect coefficients
```

**Key variables (ISSP Digital Societies module, 2024 only):**

| Variable | Question | Scale |
|---|---|---|
| `INTGAME` | How often do you use the internet for playing online video games? | 1–5 (reversed: higher = more frequent) |
| `INTSTREAM` | How often do you use the internet for streaming music or video? | 1–5 (reversed) |
| `INTSHARE` | How often do you use the internet for posting or sharing photos/videos? | 1–5 (reversed) |
| `INTMEET` | I feel more comfortable meeting new people online than in person. | 1–5 (reversed: higher = more agreement) |
| `INTLNLY` | I would feel lonely without the internet. | 1–5 (reversed) |
| `INTNEWS` | How often do you access news sources online different from your usual ones? | 1–5 (reversed) |
| `INTRUST` | How much do you trust people you have only met on the internet? | 0–10 (not reversed) |
| `INTRNETUSE` | How often did you use the internet in the past 12 months? | 1–7 (reversed) |
| `LEFTRGHT1` | Where would you place yourself on a left–right political scale? | 0–10 (not reversed) |
| `POLINT` | How interested are you personally in politics? | 1–5 (reversed) |
| `INTVIEWS` | How often do you express your political opinions on the internet? | 1–6 (reversed) |
| `GENDTECH` | Who benefits more from digital technology: women or men? | Categorical (1/2/3) |
| `AGETECH` | Who benefits more from digital technology: older or younger people? | Categorical (1/2/3) |
| `CLASSTECH` | Who benefits more from digital technology: poor or rich people? | Categorical (1/2/3) |
| `EDUCTECH` | Who benefits more from digital technology: educated or less-educated? | Categorical (1/2/3) |

> **Scale direction:** All 1–5, 1–6, and 1–7 Likert items are reversed before analysis so that higher values consistently indicate more frequent use or stronger agreement. INTRUST and LEFTRGHT1 are not reversed as they already run in the intuitive direction.

**Weights:** `WTSSNRPS` (NORC-recommended post-stratification weight for the 2024 cross-section).

**Sample sizes (young men 18–29):**

| Item | Valid N |
|---|---|
| INTRNETUSE | 111 |
| INTGAME, INTSTREAM, INTSHARE | 106 |
| INTMEET, INTLNLY, INTRUST, POLINT, INTNEWS | 105 |
| INTVIEWS | 100 |
| AGETECH | 95 |
| GENDTECH, CLASSTECH | 91 |
| EDUCTECH | 94 |
| LEFTRGHT1 | 74 |

---

#### `02_gss_trends_young_men.R`: Analysis of Trends in Opinions of Young Men

Longitudinal trend analysis using the GSS cumulative file (1972–2024). Requires `GSS7224_R1.dta`.

**Memory note:** The cumulative file has 6,000+ variables. The script uses `haven`'s `col_select` to load only the ~10 needed columns — do not attempt to load the full file.

**Outputs:**

```
05_trend_politics.png             # Fig. 05 — % Conservative and % Republican-leaning over time
06_trend_trust_happy.png          # Fig. 06 — % Can trust people and % Not too happy over time
07_trend_social.png               # Fig. 07 — % Reject trad. gender roles and % Conf. in science
09_divergence_tests.png           # Fig. 09 — Forest plot: Year × Young Male interaction coefficients
10_youth_gender_gap.png           # Fig. 10 — Young Men minus Young Women gap over time (6 variables)
table_trends_by_year_group.csv    # Weighted proportions by year and group for all trend variables
table_divergence_tests.csv        # Divergence test interaction coefficients and p-values
table_youth_gender_gap.csv        # Year-by-year M-F gap for each attitude variable
```

**Trend variables and recoding:**

| Variable | Question | Binary Indicator |
|---|---|---|
| `POLVIEWS` | Liberal–conservative self-identification (1–7) | Conservative = 1 if score 5–7 |
| `PARTYID` | Party identification (0–6) | Republican-leaning = 1 if score 4–6 |
| `TRUST` | "Most people can be trusted or can't be too careful?" | Can trust = 1 if TRUST = 1 |
| `HAPPY` | "Very happy, pretty happy, or not too happy?" | Unhappy = 1 if HAPPY = 3 |
| `FEFAM` | "Better if man works, woman stays home" (agree/disagree) | Gender egalitarian = 1 if disagree (3 or 4) |
| `CONSCI` | Confidence in the scientific community (1–3) | Hi conf. = 1 if CONSCI = 1 |

**Divergence test specification:**

```
Attitude ~ Year + YoungMale + Year×YoungMale + Male + Age
```

Year is centered at 2000 and scaled per decade. The key coefficient is the Year × Young Male interaction (β₃), interpreted as change in log-odds per decade for young men relative to the population.

**Weights:** `WTSSPS` (NORC-recommended weight for the 1972–2024 cumulative file).

---

#### `03_ref_confidence_religion.R`

Standalone reference script producing a single figure tracking confidence in organized religion (GSS variable `CONCLERG`) over time by demographic group. Used as contextual evidence in a separate chapter. Requires `GSS7224_R1.dta`.

**Variable:**

| Variable | Question | Binary Indicators |
|---|---|---|
| `CONCLERG` | Confidence in organized religion: great deal / only some / hardly any | Hi conf. = 1 if value 1; No conf. = 1 if value 3 |

**Output:**

```
ref_confidence_religion.png       # Two-panel trend plot
                                  #   Top: % "Great deal" of confidence
                                  #   Bottom: % "Hardly any" confidence
```

**Weights:** `WTSSPS`.

---

### Comparison Groups

All analyses define four demographic groups based on `SEX` (1 = male, 2 = female) and `AGE`:

| Group | Definition |
|---|---|
| Young Men (18–29) | SEX = 1, AGE 18–29 |
| Young Women (18–29) | SEX = 2, AGE 18–29 |
| Older Men (30+) | SEX = 1, AGE ≥ 30 |
| Older Women (30+) | SEX = 2, AGE ≥ 30 |

---
<br>

## YMRP Files

Replication code for the Young Men's Radicalization Pipeline (YMRP) survey analysis. The YMRP is an original cross-sectional survey of young men (ages 18–29) fielded via the YouGov opt-in panel in May 2025. It measures exposure to and trust in "manosphere" content creators, along with sexist and racist attitudes, dating history, loneliness, social media habits, and 2024 voting behavior.

---

### Data

This repository contains only the analysis code. The raw data required to replicate is:

```
data/
    YMRI_202505.csv        # YMRP survey data, YouGov panel, May 2025
```

The data file is not publicly distributed. [Contact the author](https://www.ymrp.org/contact) for access.

---

### Setup

```r
install.packages(c(
  "tidyverse",           # data wrangling and ggplot2
  "survey",              # svydesign() and weighted models
  "psych",               # alpha() and principal() for factor analysis
  "jtools",              # theme_nice()
  "marginaleffects",     # avg_slopes() and plot_predictions()
  "MASS",                # polr() for ordered logistic regression
  "gtsummary",           # tbl_regression() for formatted tables
  "gt"                   # gt tables and gtsave()
))
```

R 4.1+ required. Times New Roman must be installed for plot fonts to render correctly. See GSS setup notes above for Mac font import instructions.

---

### Files

#### `YMRP_00_setup.R`: Master Setup

Loads the raw data, constructs all derived variables, and builds the survey design object. All other YMRP scripts `source()` this file at the top. Does not produce figures or tables on its own.

**Key variables constructed:**

*Creator trust and engagement:*

| Variable | Definition |
|---|---|
| `n_trusted` | Count of manosphere creators trusted (answered "Trust" on `trust_grid_x`) |
| `n_recognized` | Count of creators recognized (familiar or following) |
| `n_following` | Count of creators followed (skeptical fan, not full trust) |
| `trust_level` | Categorical bucket: 0, 1, 2, 3+ creators trusted |
| `is_truster_binary` | Factor: "Truster" (trusts ≥ 1) vs. "Non-Truster" (reference level) |
| `fan_status` | Ordered factor: "Non-Fan" / "Skeptical Fan" / "True Believer" |
| `is_true_believer` | Binary: 1 = trusts at least one creator at highest level |

*Attitude indices (all recoded so higher = more sexist / more racist):*

| Variable | Items | Direction |
|---|---|---|
| `s1`–`s11` | Sexism battery items (11 items) | Higher = more sexist; `s4` and `s7` reverse-coded |
| `sexism_index` | Row mean of `s1`–`s11` | 1–5 scale, higher = more sexist |
| `r1`–`r3` | Racism battery items (3 items) | Higher = more racist; `r1` reverse-coded |

*Voting outcomes:*

| Variable | Definition |
|---|---|
| `vote_trump_24` | Among 2024 voters: 1 = voted Trump, 0 = voted other |
| `vote_switch_to_trump` | Among 2024 Trump voters: 1 = switcher/newly mobilized, 0 = 2020 loyalist |
| `vote_trump_new_24` | Among all 2024 voters: 1 = new Trump voter (switched or newly mobilized) |

*Dating and loneliness:*

| Variable | Definition |
|---|---|
| `loneliness` | "I often feel lonely" (`life_goals_14`), recoded so 5 = strongly agree |
| `never_relationship` | 1 if never been in a serious relationship |
| `recent_breakup` | 1 if breakup within the past 12 months |
| `hard_to_meet` | "It is hard to meet people to date" (5 = strongly agree) |
| `women_expectations` | "Women's expectations in relationships are too high" (5 = strongly agree) |

*Social media:*

| Variable | Definition |
|---|---|
| `n_platforms_used` | Count of platforms used in the past week |
| `alt_platform_user` | 1 = used any manosphere-adjacent platform (4chan, Gab, Parler, Rumble, Telegram) |
| `right_platform_user` | 1 = used X/Twitter or any alt platform |
| `hrs_youtube`, `hrs_x`, `hrs_tiktok`, etc. | Ordinal daily hours per platform (0 = don't use, 4 = 4+ hrs/day) |
| `total_social_hrs` | Sum of ordinal hours across all measured platforms |

*Controls:*

| Variable | Definition |
|---|---|
| `faminc5` | Family income (5-category quintile) |
| `educ4` | Education (4-level) |
| `race2` | Race (binary) |
| `race_label` | Race (4-category: White / Black / Hispanic / Other/Multiracial) |
| `pid3_factor` | Party ID (Democrat / Republican / Independent) |
| `pid7_with_leaners` | Party ID collapsed to 3-category factor (Dem / Rep / Ind) |
| `urbancity3` | Urbanicity (Urban / Suburban / Rural) |
| `age4` | Age in four narrow bands within 18–29 (18–20 / 21–23 / 24–26 / 27–29) |

**Creator indices:** The 11 tracked creators correspond to `trust_grid_` and `familiarity_grid_` indices 1, 2, 3, 4, 5, 10, 11, 16, 18, 19, and 24 — all Trump-endorsing manosphere figures.

**Survey design:** The `svy` object is built using `svydesign(ids = ~1, weights = ~weight, data = dat)`. The YouGov `weight` variable post-stratifies for age, race, gender, and education. All models in files 02–07 use this design.

**Scale direction:** Survey responses follow the coding 1 = Strongly Agree, 2 = Somewhat Agree, 5 = Not Sure, 3 = Somewhat Disagree, 4 = Strongly Disagree. `recode_standard()` transforms this to a 1–5 scale where 5 = Strongly Agree. `recode_reverse()` keeps 1 = Strongly Agree, used for items where agreement indicates a less sexist or less racist position.

---

#### `YMRP_01_factor_analysis.R`: Factor Analysis and Reliability

Validates the sexism and racism batteries before their use as indices in subsequent scripts. Computes Cronbach's alpha, item-drop statistics, and principal components analysis (PCA) for both batteries.

**Outputs:**

```
tables/01/YMRP_Appendix_Sexism_1Factor.csv          # 1-factor PCA loadings, communalities,
                                                    # and uniqueness for all 11 sexism items
tables/01/YMRP_Appendix_Sexism_2Factor.csv          # 2-factor varimax solution for sexism battery
                                                    # (RC1 = Traditional/Hostile; RC2 = Feminist Grievance)
tables/01/YMRP_Appendix_Racism_FactorAnalysis.csv   # 1-factor PCA loadings for 3-item racism battery
```

**Analyses:**

- **Sexism battery (s1–s11):** Cronbach's alpha; alpha-if-item-dropped for each of the 11 items; 1-factor PCA loadings and proportion of variance explained; 2-factor varimax rotation identifying a Traditional/Hostile Sexism factor (RC1) and a Feminist Grievance factor (RC2).
- **Racism battery (r1–r3):** Cronbach's alpha and 1-factor PCA loadings.

All results are printed to the console and exported to CSV. No figures are produced.

**Sexism item labels:**

| Item | Question |
|---|---|
| `s1` | Guys can't speak their minds anymore |
| `s2` | Society looks down on masculine men |
| `s3` | Men should be the breadwinner; women should stay home |
| `s4` | Women should hold more power / men should do more housework *(reversed)* |
| `s5` | Feminism favors women over men |
| `s6` | Men should be valued more in society |
| `s7` | Media is biased towards men *(reversed)* |
| `s8` | There are roles only men can do |
| `s9` | There are roles only women can do |
| `s10` | Gay men aren't really men |
| `s11` | Trans men aren't really men |

**Racism item labels:**

| Item | Question |
|---|---|
| `r1` | White privilege exists *(reversed)* |
| `r2` | Racial problems are rare in today's society |
| `r3` | Society provokes racial grievance / reverse racism |

---

#### `YMRP_02_trust_vs_sexism.R`: Creator Trust and Sexism → Trump Vote

Tests two related hypotheses: (1) that trusting more manosphere creators predicts higher sexism scores (the *dosage* hypothesis), and (2) that creator trust amplifies the relationship between sexism and Trump voting (the *mobilization* hypothesis).

**Outputs:**

```
figures/02/YMRP_Fig_Sexism_Mobilization.png         # Predicted Trump vote probability by sexism
                                                    # score, split by binary trust (Truster vs.
                                                    # Non-Truster). Two diverging lines.
figures/02/YMRP_Fig_Sexism_CountInteraction.png     # Dose-response version: one line per trust
                                                    # count (0, 1, 2, 3+ creators), showing
                                                    # steeper Trump slopes with more creators trusted
figures/02/YMRP_Fig_Sexism_by_FanStatus.png         # Violin + boxplot: sexism index distribution
                                                    # across Non-Fan, Skeptical Fan, True Believer
figures/02/YMRP_Fig_Engagement_TrumpVote.png        # Three predicted-probability lines (Recognizing
                                                    # Only, Following, Trusting) as dosage
                                                    # predictors of Trump vote
figures/02/YMRP_Fig_Sexism_by_nTrusted.png          # Scatter plot: sexism index vs. number of
                                                    # creators trusted, with OLS best-fit line
tables/02/YMRP_Model1_Dosage_Sexism.csv             # Model 1: OLS — n_trusted → sexism index
tables/02/YMRP_Model2_Mobilize_Binary.csv           # Model 2: Logistic — sexism × trust (binary)
                                                    # → Trump vote (ORs)
tables/02/YMRP_Model3_Mobilize_Count.csv            # Model 3: Logistic — sexism × n_trusted
                                                    # (count) → Trump vote (ORs)
tables/02/YMRP_Model4_Mobilize_Switchers.csv        # Model 4: Logistic — sexism × trust (binary)
                                                    # → new/switched Trump vote (ORs)
```

**Model specifications:**

| Model | Type | Outcome | Key predictor(s) |
|---|---|---|---|
| 1 (Dosage) | Weighted OLS (`svyglm`, Gaussian) | `sexism_index` | `n_trusted` |
| 2 (Mobilization, binary) | Weighted logistic (`svyglm`, quasibinomial) | `vote_trump_24` | `sexism_index × is_truster_binary` |
| 3 (Mobilization, count) | Weighted logistic | `vote_trump_24` | `sexism_index × n_trusted` |
| 4 (Switchers) | Weighted logistic | `vote_trump_new_24` | `sexism_index × is_truster_binary` |

All models control for `faminc5`, `educ4`, `race2`, `pid7_with_leaners`, `urbancity3`, and `age4`.

---

#### `YMRP_03_trust_vs_racism.R`: Creator Trust and Racism → Trump Vote

Parallel mobilization analysis for the racism battery items. Tests whether creator trust amplifies the relationship between racial attitudes and Trump voting, producing predicted probability plots for two racism items and a direct comparison of all three attitudes' conversion strength.

**Outputs:**

```
figures/03/YMRP_Fig_Racism_Mobilization_r3.png      # Predicted Trump vote probability by r3
                                                    # (reverse racism / special treatment belief),
                                                    # split by trust. Orange = Truster line.
figures/03/YMRP_Fig_Racism_Mobilization_r2.png      # Predicted Trump vote probability by r2
                                                    # (racism is rare belief), split by trust.
                                                    # Blue = Truster line.
figures/03/YMRP_Fig_AttitudeConversion_Comparison.png # Three-line comparison: predicted Trump
                                                    # vote probability across the 1–5 Likert scale
                                                    # for sexism index, r3, and r2 (controls at
                                                    # modal/mean values, no trust interaction)
```

**Models used:** Weighted logistic regressions (`svyglm`, quasibinomial) with the same control set as file 02, fit separately for `r3` and `r2` as predictors, each interacted with `is_truster_binary`. The comparison figure uses three main-effect-only models (no trust interaction) to show the raw conversion slope of each attitude into Trump votes. This script is a graph-export file; it assumes models (`model_mobilize_r3`, `model_mobilize_r2`, `mob_sex`, `mob_r3`, `mob_r2`) and `dat` are already in the environment. No CSV tables are exported here.

---

#### `YMRP_04_conversion_gap.R`: The Sexism–Racism Conversion Gap

Tests whether trust *differentially* moderates the sexism vs. racism pathways to Trump voting — i.e., whether creator trust has a uniquely strong relationship with the sexism-to-vote link compared to the racial grievance-to-vote link. Runs three formal tests plus a social media subgroup analysis.

**Outputs:**

```
figures/04/YMRP_Fig_TrustModerates_Conversion.png   # Side-by-side interaction plot: predicted
                                                    # Trump probability by attitude score × trust,
                                                    # with sexism (left panel) and racial grievance
                                                    # r3 (right panel)
figures/04/YMRP_Fig_SocialMedia_ConversionGap.png   # Forest plot: sexism vs. r3 odds ratios
                                                    # for Trump vote across social media subgroups
                                                    # (alt platform users, high social media hours,
                                                    # YouTube users, etc.), with 95% CIs
tables/04/YMRP_ModelA_Sexism_TrustModeration.csv    # Sexism × trust interaction model (ORs)
tables/04/YMRP_ModelB_r3_TrustModeration.csv        # Racial grievance × trust interaction model (ORs)
```

**Tests:**

- **Test 1A:** Compares the interaction term (attitude × trust) from the sexism model to the equivalent term in the racial grievance model. Extracts and prints main effects and interaction ORs with p-values for both.
- **Test 1B:** Stacked three-way test (`attitude_score × is_sexism × is_truster`) using a long-format dataset. The key coefficient tests whether trust differentially moderates the sexism vs. racism conversion gap.
- **Test 1C:** Informal mediation check — measures the percentage drop in each attitude coefficient when `n_trusted` is added as a covariate, indicating how much of each attitude's link to Trump voting runs through creator trust.
- **Test 2:** Social media subgroups — re-runs both conversion models within eight pre-defined subgroups (alt platform users, X/right platform users, high vs. low social media hours, YouTube users vs. non-users) and compares the resulting ORs.

---

#### `YMRP_05_trust_vs_dating.R`: Dating History, Loneliness, and Manosphere Involvement

Tests whether romantic history and loneliness predict manosphere involvement, using three model specifications with different operationalizations of the outcome.

**Outputs:**

```
tables/05/YMRP_ModelA_TrueBeliever_Binary.csv       # Model A: Binary logistic — predictors
                                                    # of True Believer status (ORs)
tables/05/YMRP_ModelC_Dosage_nTrusted.csv           # Model C: OLS — predictors of number
                                                    # of creators trusted (coefficients)
```

**Model specifications:**

| Model | Type | Outcome | Key predictors |
|---|---|---|---|
| A (Binary) | Weighted logistic (`svyglm`, quasibinomial) | `is_true_believer` | `loneliness`, `never_relationship`, `recent_breakup` |
| B (Ordered) | Weighted ordered logistic (`svyolr`) | `fan_status` (Non-Fan / Skeptical Fan / True Believer) | same |
| C (Dosage) | Weighted OLS (`svyglm`, Gaussian) | `n_trusted` | same |

All models include the standard control set (`faminc5`, `educ4`, `race2`, `pid7_with_leaners`, `urbancity3`, `age4`). Model B (ordered logit) results are printed to the console with p-values derived from a t-based approximation; it is not exported to CSV. A key findings summary is printed to the console with ORs and percentage changes for each romantic history predictor under Model A and coefficient magnitudes under Model C.

---

#### `YMRP_06_creator_ladder.R`: The Creator Engagement Ladder

Formalizes the four-level creator engagement hierarchy (no recognition → recognition only → following → trusting) and tests whether each level independently predicts Trump voting, controlling for the others.

**Outputs:**

```
figures/06/YMRP_Fig_Creator_Ladder.png              # Bar chart: predicted Trump vote probability
                                                    # at each of the four engagement levels
                                                    # (no recognition, recognizes only, follows,
                                                    # trusts), with 95% CIs
figures/06/YMRP_Fig_Engagement_TrumpVote.png        # Three predicted-probability lines from
                                                    # the ladder model, varying n_recognized_only,
                                                    # n_followed, and n_trusted across 0–11
tables/06/YMRP_Model11_CreatorLadder_Counts.csv     # Model 1: Logistic — n_recognized_only,
                                                    # n_followed, n_trusted simultaneously →
                                                    # Trump vote (ORs and marginal effects)
tables/06/YMRP_Model12_CreatorLadder_Categorical.csv # Model 2: Logistic — categorical ladder
                                                    # group (0_None ref) → Trump vote (ORs)
```

**Model specifications:**

| Model | Type | Outcome | Key predictor(s) |
|---|---|---|---|
| 1 (Counts) | Weighted logistic | `vote_trump_24` | `n_recognized_only`, `n_followed`, `n_trusted` simultaneously |
| 2 (Categorical) | Weighted logistic | `vote_trump_24` | `ladder_group` (0_None / 1_Recognizes / 2_Follows / 3_Trusts) |
| 3 (Switching) | Weighted logistic | `vote_switch_to_trump` | `n_recognized_only`, `n_followed`, `n_trusted` |

**Engagement ladder groups:**

| Group | Definition |
|---|---|
| `0_None` | Does not recognize any of the 11 tracked creators |
| `1_Recognizes` | Recognizes at least one but does not follow any |
| `2_Follows` | Follows at least one but trusts none |
| `3_Trusts` | Trusts at least one (True Believer) |

Model 1 also reports average marginal effects (percentage-point change in Trump vote probability per additional creator at each engagement level) via `avg_slopes()`. Predicted probabilities for each categorical ladder group are printed to the console. Model 3 (vote switching) runs conditionally and is skipped if `vote_switch_to_trump` is absent from the data.

---

#### `YMRP_07_sexism_by_race.R`: Sexism and Creator Trust by Race

Describes variation in sexism scores and creator trust levels across racial groups, and tests whether racial differences in sexism are statistically significant after adjusting for socioeconomic controls.

**Outputs:**

```
figures/07/YMRP_Fig_Trust_by_Race.png               # Stacked proportional bar chart: share of
                                                    # each racial group at each trust level
                                                    # (0, 1, 2, 3+ creators trusted)
figures/07/YMRP_Fig_Sexism_by_Race.png              # Violin + boxplot: sexism index distribution
                                                    # by race, ordered by mean score
figures/07/YMRP_Fig_Pipeline_by_Race.png            # Boxplot: sexism index × trust level,
                                                    # faceted by race (4 panels) — shows whether
                                                    # the trust–sexism dosage staircase holds
                                                    # across racial groups
tables/07/YMRP_Model7_Sexism_by_Race.csv            # Adjusted OLS — race_label → sexism index
                                                    # (coefficients, vs. White reference)
tables/07/YMRP_WeightedMeans_Sexism_by_Race.csv     # Weighted mean sexism index and SE by race
tables/07/YMRP_TrustDistribution_by_Race.csv        # Weighted % at each trust level by race
                                                    # (wide format, one column per trust level)
```

**Analyses:**

- **A. Weighted crosstab:** `svytable()` row-percentage breakdown of trust level by race.
- **B. Weighted means and medians:** `svyby()` for mean and median sexism index within each racial group.
- **C. Weighted ANOVA:** Unadjusted model (`sexism_index ~ race_label`) and adjusted model (`sexism_index ~ race_label + faminc5 + educ4 + pid7_with_leaners + urbancity3 + age4`), with an F-test on the race term via `regTermTest()`.
- **D. Item-by-item breakdown:** Weighted mean for each of the 11 sexism items (`s1`–`s11`) by racial group.

Note that `race2` (the binary race control used in most other models) is replaced here by `race_label` (4-category: White / Black / Hispanic / Other/Multiracial) as the variable of interest. White is set as the reference category.

---

### Weights

YouGov `weight` variable, post-stratifying for age, race, gender, and education. Applied throughout via the `svy` survey design object built in `YMRP_00_setup.R`.

### Creator Indices Tracked

11 Trump-endorsing manosphere figures, corresponding to `trust_grid_` and `familiarity_grid_` column indices 1, 2, 3, 4, 5, 10, 11, 16, 18, 19, and 24 in the raw data.

### Voting Eligibility

Respondents born after 2006 (`birthyr > 2006`) are treated as ineligible for the 2024 election and assigned `NA` on all vote outcome variables. Because only birth year (not birth month or day) is available, this cutoff is conservative — a small number of respondents born late in 2006 may have been eligible but are excluded.

---

## Thesis

The thesis discussing the results of this project is accessible through [Wesleyan's Special Collections & Archives](https://digitalcollections.wesleyan.edu/islandora/object/wesleyanct-etd_hon_theses?).