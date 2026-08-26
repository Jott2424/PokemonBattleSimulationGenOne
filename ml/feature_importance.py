"""
Loads the trained model and prints the top features by importance.
Doesn't need the training data — just the saved model + its feature list.

Usage (run from ml/; defaults point at v1/, pass --model/--features to target v2):
    python feature_importance.py [--top N] [--type gain|weight|cover|total_gain|total_cover]
"""
import argparse
import json
import os

import xgboost as xgb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.path.join(os.path.dirname(__file__), "v1", "win_probability_model.json"))
    parser.add_argument("--features", default=os.path.join(os.path.dirname(__file__), "v1", "win_probability_model_features.json"))
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--type", default="gain", choices=["gain", "weight", "cover", "total_gain", "total_cover"])
    args = parser.parse_args()

    with open(args.features) as f:
        feature_cols = json.load(f)["feature_cols"]

    model = xgb.XGBClassifier()
    model.load_model(args.model)
    booster = model.get_booster()
    booster.feature_names = feature_cols

    scores = booster.get_score(importance_type=args.type)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    print(f"Top {args.top} features by '{args.type}' "
          f"({len(scores)} of {len(feature_cols)} features used at all in the ensemble):\n")
    for i, (name, score) in enumerate(ranked[:args.top], 1):
        print(f"{i:3d}. {score:10.2f}  {name}")


if __name__ == "__main__":
    main()
