"""
Trains the win-probability model on the Parquet file extract_features.py
produces.

Split strategy: grouped by unordered trainer PAIR (not battle, not row) —
every row involving a given pair of trainers, across all logic-profile
combos, all 10 samples, and both subject/opponent directions, lands in
the same split. This is what makes the held-out test set a genuine test
of generalization to trainer combinations the model has never seen,
rather than just new RNG rolls or new profile pairings of a matchup it
already trained on.

Excluded from the feature matrix (present in the Parquet file for
traceability/other uses, but never shown to the model):
  - battle_id, subject_trainer_id, opponent_trainer_id — identifiers,
    meaningless for trainer pairs the model hasn't seen
  - total_turns — only known *after* a battle happens; using it would
    leak information a real pre-battle prediction could never have
  - label_win — the target itself

Usage (run from ml/; defaults point at v1/, pass --data/--out to target v2):
    python train_model.py [--data FILE] [--out FILE] [--test-frac F] [--val-frac F]
    python train_model.py --data v2/training_data.parquet --out v2/win_probability_model.json
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import xgboost as xgb

NON_FEATURE_COLS = {
    "battle_id", "subject_trainer_id", "opponent_trainer_id", "total_turns", "label_win",
}


def _pair_key(df: pd.DataFrame) -> pd.Series:
    """Unordered trainer-pair key, independent of subject/opponent direction."""
    lo = np.minimum(df["subject_trainer_id"], df["opponent_trainer_id"])
    hi = np.maximum(df["subject_trainer_id"], df["opponent_trainer_id"])
    return lo.astype(str) + "_" + hi.astype(str)


def split_by_pair(df: pd.DataFrame, test_frac: float, val_frac: float, seed: int):
    """Splits so every row for a given trainer pair lands in exactly one of
    train/val/test — never split across them."""
    pairs = _pair_key(df)
    unique_pairs = pairs.drop_duplicates().values
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_pairs)

    n = len(unique_pairs)
    n_test = int(n * test_frac)
    n_val = int(n * val_frac)
    test_pairs = set(unique_pairs[:n_test])
    val_pairs = set(unique_pairs[n_test:n_test + n_val])
    # remaining pairs are train

    is_test = pairs.isin(test_pairs)
    is_val = pairs.isin(val_pairs) & ~is_test
    is_train = ~is_test & ~is_val
    return df[is_train], df[is_val], df[is_test]


def _log_loss(y, p, eps=1e-12):
    # Cast to float64 before clipping — predict_proba returns float32, whose
    # precision near 1.0 (~1e-7) is coarser than eps, so clipping in float32
    # silently fails to keep p away from exactly 0/1 and produces log(0).
    p = np.clip(p.astype(np.float64), eps, 1 - eps)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


def _roc_auc(y, p):
    """Probability that a random positive scores higher than a random negative,
    via the rank-sum (Mann-Whitney U) identity — avoids pulling in sklearn."""
    y = np.asarray(y)
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def evaluate(model, X, y, label):
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    y = np.asarray(y)
    accuracy = np.mean(pred == y)
    brier = np.mean((proba - y) ** 2)
    print(f"  {label}: n={len(y)}  "
          f"accuracy={accuracy:.4f}  "
          f"log_loss={_log_loss(y, proba):.4f}  "
          f"auc={_roc_auc(y, proba):.4f}  "
          f"brier={brier:.4f}")
    return proba


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "v1", "training_data.parquet"))
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "v1", "win_probability_model.json"))
    parser.add_argument("--test-frac", type=float, default=0.15)
    parser.add_argument("--val-frac", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1, help="-1 = use all available cores")
    args = parser.parse_args()

    print(f"Loading {args.data} ...")
    df = pd.read_parquet(args.data)
    print(f"  {len(df)} rows x {len(df.columns)} columns")

    feature_cols = [c for c in df.columns if c not in NON_FEATURE_COLS]
    cat_cols = [c for c in feature_cols if str(df[c].dtype) == "category"]
    print(f"  {len(feature_cols)} features ({len(cat_cols)} categorical: {cat_cols})")

    print("Splitting by trainer pair (train/val/test never share a pair)...")
    train_df, val_df, test_df = split_by_pair(df, args.test_frac, args.val_frac, args.seed)
    print(f"  train={len(train_df)}  val={len(val_df)}  test={len(test_df)}")

    X_train, y_train = train_df[feature_cols], train_df["label_win"]
    X_val, y_val = val_df[feature_cols], val_df["label_win"]
    X_test, y_test = test_df[feature_cols], test_df["label_win"]

    print("Training XGBoost (tree_method=hist, CPU)...")
    model = xgb.XGBClassifier(
        tree_method="hist",
        enable_categorical=True,
        n_jobs=args.n_jobs,
        n_estimators=1000,
        early_stopping_rounds=30,
        eval_metric="logloss",
        objective="binary:logistic",
        random_state=args.seed,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=50)
    print(f"  best iteration: {model.best_iteration}")

    print("Evaluating...")
    evaluate(model, X_train, y_train, "train")
    evaluate(model, X_val, y_val, "val  ")
    evaluate(model, X_test, y_test, "test ")

    print(f"Saving model to {args.out}")
    model.save_model(args.out)
    meta_path = args.out.rsplit(".", 1)[0] + "_features.json"
    with open(meta_path, "w") as f:
        json.dump({"feature_cols": feature_cols, "categorical_cols": cat_cols}, f, indent=2)
    print(f"Saved feature list to {meta_path}")
    print("Done.")


if __name__ == "__main__":
    main()
