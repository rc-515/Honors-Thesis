################################################################################
# Quick reference: Confidence in Organized Religion over time
# GSS variable: CONCLERG
# 1 = A great deal, 2 = Only some, 3 = Hardly any
################################################################################

library(haven)
library(tidyverse)
library(labelled)
library(survey)
library(srvyr)
library(scales)
library(patchwork)

# ── Load data ────────────────────────────────────────────────────────────────
dta_path <- "gss_cumulative.dta"

all_names <- names(haven::read_dta(dta_path, n_max = 0))
name_lookup <- setNames(all_names, toupper(all_names))

keep <- c("year", "age", "sex", "wtssps", "conclerg")
select_these <- unname(name_lookup[toupper(keep)])
select_these <- select_these[!is.na(select_these)]

gss <- haven::read_dta(dta_path, col_select = all_of(select_these))
names(gss) <- toupper(names(gss))

gss <- gss %>%
  mutate(across(where(is.labelled), ~ as.numeric(.x))) %>%
  mutate(
    male = as.integer(SEX == 1),
    group4 = case_when(
      male == 1 & AGE >= 18 & AGE <= 29 ~ "Young Men (18-29)",
      male == 0 & AGE >= 18 & AGE <= 29 ~ "Young Women (18-29)",
      male == 1 & AGE >= 30             ~ "Older Men (30+)",
      male == 0 & AGE >= 30             ~ "Older Women (30+)"
    ),
    # Recode: proportion with "a great deal" of confidence
    hi_conf_relig = case_when(CONCLERG == 1 ~ 1L, CONCLERG %in% 2:3 ~ 0L),
    # Recode: proportion with "hardly any" confidence
    no_conf_relig = case_when(CONCLERG == 3 ~ 1L, CONCLERG %in% 1:2 ~ 0L)
  ) %>%
  rename(wt = WTSSPS) %>%
  filter(!is.na(group4), !is.na(wt), wt > 0)

cat("Loaded:", nrow(gss), "respondents\n")

# ── Global theme (mirrors GSS 2024 / YMRP files exactly) ─────────────────────
theme_set(
  theme_minimal(base_size = 16, base_family = "Times New Roman") +
    theme(
      panel.grid.minor = element_blank(),
      plot.title       = element_text(face = "bold", size = 18),
      plot.subtitle    = element_text(size = 15, colour = "grey40"),
      plot.caption     = element_text(size = 15),
      axis.text        = element_text(size = 15),
      axis.text.x      = element_text(size = 15, margin = margin(t = 4)),
      axis.title       = element_text(size = 16),
      legend.text      = element_text(size = 15),
      strip.text       = element_text(face = "bold", size = 17),
      legend.position  = "bottom",
      plot.margin      = margin(t = 5, r = 10, b = 5, l = 5, unit = "pt")
    )
)

# ── Palette (mirrors GSS 2024 file) ──────────────────────────────────────────
pal <- c(
  "Young Men (18-29)"   = "#E63946",
  "Young Women (18-29)" = "#457B9D",
  "Older Men (30+)"     = "#F4A261",
  "Older Women (30+)"   = "#2A9D8F"
)

# ── Compute trends ────────────────────────────────────────────────────────────
compute <- function(data, varname) {
  data %>%
    filter(!is.na(.data[[varname]])) %>%
    as_survey_design(weights = wt) %>%
    group_by(YEAR, group4) %>%
    summarise(
      prop   = survey_mean(.data[[varname]], vartype = "se"),
      n_cell = unweighted(n())
    ) %>%
    ungroup() %>%
    filter(n_cell >= 15) %>%
    mutate(variable = varname)
}

trends <- bind_rows(
  compute(gss, "hi_conf_relig"),
  compute(gss, "no_conf_relig")
)

# ── Plot function ─────────────────────────────────────────────────────────────
plot_it <- function(data, varname, title) {
  d <- data %>% filter(variable == varname)
  ggplot(d, aes(x = YEAR, y = prop, colour = group4, fill = group4)) +
    annotate("rect", xmin = 2000, xmax = max(d$YEAR),
             ymin = -Inf, ymax = Inf, fill = "grey90", alpha = 0.4) +
    annotate("text", x = 2000, y = max(d$prop + d$prop_se, na.rm = TRUE),
             label = "Internet era \u2192", hjust = 0, size = 4.5,
             colour = "grey50", fontface = "italic",
             family = "Times New Roman") +
    geom_line(alpha = 0.3, linewidth = 0.3) +
    geom_smooth(method = "loess", span = 0.45, se = FALSE, linewidth = 1.2) +
    scale_colour_manual(values = pal, name = NULL) +
    scale_fill_manual(values   = pal, name = NULL) +
    scale_y_continuous(labels = percent_format(accuracy = 1)) +
    labs(title = title, x = NULL, y = NULL)
}

p2 <- plot_it(trends, "no_conf_relig",
              "% \u2018Hardly any\u2019 confidence in organized religion")

# ── Combine with patchwork ────────────────────────────────────────────────────
panel <- p2 +
  plot_annotation(
    title    = "Confidence in Organized Religion: Young Men vs. Everyone Else",
    subtitle = "GSS 1972\u20132024 \u00B7 Loess-smoothed weighted proportions \u00B7 Grey band = internet era (2000+)",
    caption  = "Source: GSS Cumulative File \u00B7 Weight: WTSSPS",
    theme    = theme(
      plot.title    = element_text(face = "bold", size = 20,
                                   family = "Times New Roman"),
      plot.subtitle = element_text(size = 13, colour = "grey40",
                                   family = "Times New Roman"),
      plot.caption  = element_text(size = 13, family = "Times New Roman")
    )
  )

ggsave("ref_confidence_religion.png", panel, width = 12, height = 7, dpi = 300)
cat("Saved: ref_confidence_religion.png\n")

# ── Print table ───────────────────────────────────────────────────────────────

cat("\n\u2500\u2500 % 'Great deal' confidence in organized religion \u2500\u2500\n\n")
trends %>%
  filter(variable == "hi_conf_relig") %>%
  select(YEAR, group4, prop) %>%
  mutate(prop = round(prop * 100, 1)) %>%
  pivot_wider(names_from = group4, values_from = prop) %>%
  as.data.frame() %>%
  print(row.names = FALSE)

cat("\n\u2500\u2500 % 'Hardly any' confidence in organized religion \u2500\u2500\n\n")
trends %>%
  filter(variable == "no_conf_relig") %>%
  select(YEAR, group4, prop) %>%
  mutate(prop = round(prop * 100, 1)) %>%
  pivot_wider(names_from = group4, values_from = prop) %>%
  as.data.frame() %>%
  print(row.names = FALSE)