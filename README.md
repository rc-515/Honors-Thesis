# Code for Honors Thesis on Online Radicalization Pathways and Cultures, written by Rowan Cahill. Submitted April 16, 2026.
Any questions can be directed to contact@rowancahill.com.

## Outline

This repository contains analysis code for three empirical chapters of this Thesis. 

```
Chapter 3/
    GSS/
        01gss_habitual_analysis.R
        02gss_trend_analysis.R
        03gss_religion.R
    YMRP/
        YMRP_00_setup.R
        YMRP_01_factor_analysis.R
        YMRP_02_trust_vs_sexism.R
        YMRP_03_trust_vs_racism.R
        YMRP_04_conversion_gap.R
        YMRP_05_trust_vs_dating.R
        YMRP_06_creator_ladder.R
        YMRP_07_sexism_by_race.R
Chapter 4/
Chapter 5/
    emote_clean.py
    master_pipeline.py
    multi_model_compare.py
    plot_distributions.py
    README.md
    roberta_analysis.py
    stream_hours.py
    toxic_spans.py
    twitch_score.py
    user_profiles.py
    viewership_analysis.py
```

Each chapter folder has its own README.md, explaining the functions of each code. 

## Chapter 3: Behaviors and Attitudes of Young Men

Chapter 3 uses two survey datasets to assess how young men differ from the broader population in their digital habits, social attitudes, and political orientations. The first half draws on the 2024 General Social Survey (GSS), using both cross-sectional and 50-year trend analysis to examine shifts in young men's conservatism, happiness, gender-role attitudes, and institutional trust. The second half draws on a May 2025 survey from the Young Men Research Project (YMRP), a YouGov-fielded poll of 1,079 men aged 18–29, to assess how trust in right-wing online creators correlates with sexist and racially resentful attitudes and with Trump voting behavior.

## Chapter 4: Pipelines for Men on Instagram

Chapter 4 conducts a sock puppet audit of Instagram Reels to assess whether the platform's recommendation algorithm treats accounts of different genders differently, surfaces political or extreme content to new users, and shifts its recommendations when an account engages with right-leaning creators. Four accounts were created and automated using Genymotion and Appium, and collected reels were analyzed using a multimodal pipeline combining Whisper transcription and Google Gemini frame analysis.

## Chapter 5: Behavior in Right-Leaning Spaces

Chapter 5 analyzes over 8.5 million livestream chat messages from five right-leaning creators on the streaming platform Kick. The code can be used to replicate this scoring and analysis against viewership and other features. Toxicity scoring is performed using the Detoxify library, cross-validated against Meta's RoBERTa hate speech classifier and Google Gemini. The chapter tracks toxicity by streamer, stream duration, viewership, and user tenure.

---

## Thesis

The Thesis discussing the results of this project is accessible through [Wesleyan's Special Collections & Archives](https://digitalcollections.wesleyan.edu/islandora/object/wesleyanct-etd_hon_theses?).

This repo also contains **the Appendix for the Thesis, contained in `Appendix.pdf`.**


## Disclaimers

Raw Data will not be published in this repository, but each chapter will note exactly where the raw data can be found. All was publicly available or collectable except for the YMRP data, which was given upon request.

> **Note:** Tools from Anthropic were used to assist in the formalizing of this code.