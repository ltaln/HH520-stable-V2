from analysis.match_analysis import analyze_match
from formatter.output_formatter import build_display_row


def _full_match():
    return {
        "match_id":"fd1","home_team":"Home","away_team":"Away","league":"TEST",
        "market":{"home_odds":2.20,"draw_odds":3.20,"away_odds":3.30},
        "possession":{"home":52,"away":48},
        "research_factors":{
            "home_attack":1.1,"away_attack":1.0,
            "home_defense":1.0,"away_defense":1.1,
            "home_h2h":1.0,"away_h2h":1.0,
            "home_form":1.1,"away_form":0.9,
        },
        "goal_timing":{
            "available":True,"timing_mode":"six_bin","source_domain":"footystats.org",
            "home":{
                "first_half_gf_signal":0.48,"first_half_ga_signal":0.44,
                "profile_stats":{
                    "shots":13.0,"shots_on_target":5.2,"shot_conversion":0.12,
                    "wins_rate":0.52,"draws_rate":0.25,"losses_rate":0.23,
                },
            },
            "away":{
                "first_half_gf_signal":0.41,"first_half_ga_signal":0.51,
                "profile_stats":{
                    "shots":10.5,"shots_on_target":3.7,"shot_conversion":0.10,
                    "wins_rate":0.31,"draws_rate":0.28,"losses_rate":0.41,
                },
            },
        },
    }


def test_full_data_activates_all_three_layers_and_label():
    m=_full_match()
    a=analyze_match(m)
    assert a["data_mode"]["mode"]=="FULL_DATA"
    assert a["probability"]["full_data_probability_used"] is True
    assert "COLLECTION1_1" in a["score"]["model"]
    assert "COLLECTION1_1" in a["htft"]["model"]
    assert a["htft"]["timing_used"] is True


def test_incomplete_external_data_falls_back_to_10027_only():
    m=_full_match()
    m["goal_timing"]["away"]["profile_stats"]={}
    a=analyze_match(m)
    assert a["data_mode"]["mode"]=="10027_ONLY"
    assert a["probability"]["full_data_probability_used"] is False
    assert a["score"]["model"]=="HDA_POISSON_V1"
    assert a["htft"]["timing_used"] is False


def test_output_row_marks_data_mode():
    pred={
        "home_team":"A","away_team":"B","direction":"主胜","state":"CONFIRM",
        "market_probability":0.6,"score1":"1:0","score2":"2:0",
        "score1_probability":0.2,"score2_probability":0.1,
        "htft1":"主/主","htft2":"平/主","htft1_probability":0.3,"htft2_probability":0.2,
        "total_goals":"2球","total_goals_probability":0.25,"data_mode":"FULL_DATA",
    }
    row=build_display_row(pred)
    assert "[全数据]" in row["球队对阵"]
