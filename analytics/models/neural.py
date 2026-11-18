"""Stage 4b, Step 39: small neural networks (an additional modelling experiment): MLP, LSTM, GRU, 1D CNN.

Rows: the identical eligible rows and splits as Stage 4a. Training rows are split in time:
  fit part        eligible training rows dated before the early-stopping start: the ONLY rows any network,
                  encoder or scaler learns from
  stop part       eligible training rows inside the early-stopping range: used only to decide when to stop
  validation      never seen in training or stopping; selection only (as for the Random Forest)
Inputs per row:
  sequence (28, 2)  scaled boardings for D-28..D-1 (missing day -> 0 in scaled units = training mean) + observed
  static            route one-hot (unseen routes -> all zeros) + standardized day_of_week, month, is_weekend,
                    is_sunday_like_day: the same route and calendar inputs as the tabular models
Target: boardings scaled with the fit-part mean/std; predictions are inverse-scaled and floored at 0.
Determinism: fixed seed before each model, seeded shuffling, deterministic algorithms, one thread, CPU, float32.
Saved files hold weights as numpy arrays + the fitted preprocessor + config (no pickled torch objects).
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from torch import nn

from analytics.models.regressors import training_rows
from analytics.models.sequences import build_sequences

CALENDAR = ["day_of_week", "month", "is_weekend", "is_sunday_like_day"]
ARCHITECTURES = ["mlp", "lstm", "gru", "cnn"]
PAYLOAD_FORMAT = "stage4b-network-1"


class FairnessError(ValueError):
    pass


# ---------------------------------------------------------------- rows
def training_parts(features: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split eligible TRAINING rows into the fit part and the early-stopping part. Nothing else is returned."""
    train = training_rows(features)
    es = cfg["periods"]["early_stopping"]
    start, end = pd.Timestamp(es["start"]), pd.Timestamp(es["end"])
    if end != pd.Timestamp(cfg["periods"]["train_end"]):
        raise FairnessError("the early-stopping range must end on the last training day")
    fit = train[train["date"] < start]
    stop = train[(train["date"] >= start) & (train["date"] <= end)]
    assert_training_only(fit, cfg)
    assert_training_only(stop, cfg)
    if len(fit) + len(stop) != len(train):
        raise FairnessError("fit + stop parts must cover the eligible training rows exactly")
    return fit, stop


def assert_training_only(rows: pd.DataFrame, cfg: dict) -> None:
    if not (rows["split"].eq("train").all() and rows["eligible"].astype(bool).all()
            and rows["date"].le(pd.Timestamp(cfg["periods"]["train_end"])).all()):
        raise FairnessError("only eligible training rows may reach training, early stopping or the scalers")


# ---------------------------------------------------------------- preprocessing
class NeuralPreprocessor:
    """Learned state, fitted on the fit part only: route encoder, calendar scaler, boardings mean/std."""

    def fit(self, rows: pd.DataFrame, cfg: dict) -> "NeuralPreprocessor":
        assert_training_only(rows, cfg)
        self.length = int(cfg["sequence"]["length_days"])
        self.placeholder = float(cfg["sequence"]["missing_placeholder_scaled"])
        self.encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False).fit(rows[["route"]])
        self.calendar = StandardScaler().fit(rows[CALENDAR].astype(float))
        y = rows["rides"].to_numpy(dtype=float)
        self.mean, self.std = float(y.mean()), float(y.std())
        self.fitted_rows = int(len(rows))
        return self

    @property
    def static_dim(self) -> int:
        return len(self.encoder.categories_[0]) + len(CALENDAR)

    def transform(self, rows: pd.DataFrame, raw: np.ndarray, observed: np.ndarray) -> tuple[torch.Tensor, torch.Tensor]:
        value = (raw - self.mean) / self.std
        value = np.where(observed > 0, value, self.placeholder)  # missing day: placeholder, flagged by observed=0
        seq = np.stack([value, observed], axis=-1).astype(np.float32)
        static = np.hstack([self.encoder.transform(rows[["route"]]),
                            self.calendar.transform(rows[CALENDAR].astype(float))]).astype(np.float32)
        return torch.from_numpy(seq), torch.from_numpy(static)

    def scale_target(self, rides) -> torch.Tensor:
        return torch.from_numpy(((np.asarray(rides, dtype=float) - self.mean) / self.std).astype(np.float32))

    def unscale(self, out: np.ndarray) -> np.ndarray:
        return out.astype(np.float64) * self.std + self.mean


# ---------------------------------------------------------------- networks
def _head(n_in: int, hidden: int) -> nn.Sequential:
    return nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, 1))


class MLP(nn.Module):
    def __init__(self, length: int, static_dim: int, a: dict):
        super().__init__()
        h1, h2 = a["hidden"]
        self.net = nn.Sequential(nn.Linear(length * 2 + static_dim, h1), nn.ReLU(), _head(h1, h2))

    def forward(self, seq, static):
        return self.net(torch.cat([seq.flatten(1), static], dim=1)).squeeze(1)


class Recurrent(nn.Module):
    def __init__(self, kind: str, static_dim: int, a: dict):
        super().__init__()
        cell = nn.LSTM if kind == "lstm" else nn.GRU
        self.rnn = cell(input_size=2, hidden_size=a["hidden_size"], num_layers=a["num_layers"], batch_first=True)
        self.head = _head(a["hidden_size"] + static_dim, a["head_hidden"])

    def forward(self, seq, static):
        _, h = self.rnn(seq)
        last = (h[0] if isinstance(h, tuple) else h)[-1]  # final hidden state after reading D-28 .. D-1
        return self.head(torch.cat([last, static], dim=1)).squeeze(1)


class CNN(nn.Module):
    def __init__(self, static_dim: int, a: dict):
        super().__init__()
        layers, c_in = [], 2
        for _ in range(a["conv_layers"]):
            layers += [nn.Conv1d(c_in, a["channels"], a["kernel_size"]), nn.ReLU()]
            c_in = a["channels"]
        self.conv = nn.Sequential(*layers)
        self.head = _head(a["channels"] + static_dim, a["head_hidden"])

    def forward(self, seq, static):
        z = self.conv(seq.transpose(1, 2)).mean(dim=2)  # global average over time
        return self.head(torch.cat([z, static], dim=1)).squeeze(1)


def make_network(name: str, length: int, static_dim: int, cfg: dict) -> nn.Module:
    a = cfg["architectures"][name]
    if name == "mlp":
        return MLP(length, static_dim, a)
    if name in ("lstm", "gru"):
        return Recurrent(name, static_dim, a)
    if name == "cnn":
        return CNN(static_dim, a)
    raise ValueError(f"unknown architecture {name}")


def parameter_count(model: nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters()))


# ---------------------------------------------------------------- determinism and training
def set_deterministic(cfg: dict) -> None:
    d = cfg["deterministic"]
    torch.manual_seed(int(cfg["seed"]))
    torch.use_deterministic_algorithms(bool(d["use_deterministic_algorithms"]))
    torch.set_num_threads(int(d["num_threads"]))
    if torch.get_num_interop_threads() != int(d["num_interop_threads"]):
        try:
            torch.set_num_interop_threads(int(d["num_interop_threads"]))
        except RuntimeError:  # can only be set once per process, before any parallel work
            pass


def train_network(name: str, prep: NeuralPreprocessor, fit_inputs, stop_inputs, cfg: dict):
    """fit_inputs / stop_inputs: (seq, static, target) tensors. Returns (best model, history, summary)."""
    t = cfg["training"]
    set_deterministic(cfg)  # same seed before EVERY model: same starting RNG state
    model = make_network(name, prep.length, prep.static_dim, cfg)
    opt = torch.optim.Adam(model.parameters(), lr=t["learning_rate"])
    loss_fn = nn.MSELoss()
    rng = np.random.default_rng(int(cfg["seed"]))
    seq, static, y = fit_inputs
    s_seq, s_static, s_y = stop_inputs
    n, bs = len(y), int(t["batch_size"])
    best, best_state, best_epoch, since, history = float("inf"), None, 0, 0, []
    for epoch in range(1, int(t["max_epochs"]) + 1):
        model.train()
        order = torch.from_numpy(rng.permutation(n))
        total = 0.0
        for i in range(0, n, bs):
            idx = order[i:i + bs]
            opt.zero_grad()
            loss = loss_fn(model(seq[idx], static[idx]), y[idx])
            loss.backward()
            opt.step()
            total += loss.detach().item() * len(idx)
        model.eval()
        with torch.no_grad():
            stop_loss = float(loss_fn(model(s_seq, s_static), s_y))
        history.append({"model": name, "epoch": epoch, "fit_loss": total / n, "stop_loss": stop_loss})
        if stop_loss < best:
            best, best_epoch, since = stop_loss, epoch, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            since += 1
            if since >= int(t["early_stopping_patience"]):
                break
    model.load_state_dict(best_state)
    model.eval()
    summary = {"epochs_run": len(history), "best_epoch": best_epoch, "best_stop_loss": best,
               "parameters": parameter_count(model)}
    return model, history, summary


# ---------------------------------------------------------------- prediction, saving, loading
def make_nn_predictor(model: nn.Module, prep: NeuralPreprocessor, history: pd.DataFrame, floor: float = 0.0,
                      reporting_delay_days: int = 1):
    """predict(frame): rebuild the 28-day windows from history for these rows, forward one row at a time, unscale, floor."""
    def predict(frame: pd.DataFrame) -> np.ndarray:
        raw, observed = build_sequences(frame, history, prep.length, reporting_delay_days)
        seq, static = prep.transform(frame, raw, observed)
        # one row at a time: every row takes the identical computation however the caller groups rows, so a
        # one-day replay and a full-period run give bit-identical forecasts (float32 results depend on batch size)
        with torch.no_grad():
            out = np.concatenate([model(seq[i:i + 1], static[i:i + 1]).numpy() for i in range(len(seq))]) \
                if len(seq) else np.empty(0, dtype=np.float32)
        return np.maximum(prep.unscale(out), floor)
    return predict


def network_payload(name: str, model: nn.Module, prep: NeuralPreprocessor, cfg: dict, summary: dict) -> dict:
    return {"format": PAYLOAD_FORMAT, "architecture": name, "architecture_config": cfg["architectures"][name],
            "length": prep.length, "static_dim": prep.static_dim,
            "state": {k: v.detach().cpu().numpy().copy() for k, v in model.state_dict().items()},
            "preprocessor": prep, "summary": {k: v for k, v in summary.items() if k != "train_seconds"},
            "seed": cfg["seed"],
            "artifact_version": cfg["artifact_version"], "torch_version": torch.__version__}


def load_network(payload: dict) -> tuple[nn.Module, NeuralPreprocessor]:
    if payload.get("format") != PAYLOAD_FORMAT:
        raise ValueError("not a Stage 4b network file")
    cfg = {"architectures": {payload["architecture"]: payload["architecture_config"]}}
    model = make_network(payload["architecture"], payload["length"], payload["static_dim"], cfg)
    model.load_state_dict({k: torch.from_numpy(np.array(v)) for k, v in payload["state"].items()})
    model.eval()
    return model, payload["preprocessor"]
