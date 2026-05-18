#!/usr/bin/env python3
"""
Benchmark de detecção de tonalidade — calibração do SoundGrabber.

Testa cada perfil Essentia individualmente + o sistema de votação atual
contra a tonalidade conhecida de músicas famosas. Usa os resultados para
sugerir os pesos ideais de votação.

Uso:
    python tests/benchmark_key.py
    python tests/benchmark_key.py --keep    # mantém os WAVs após o teste
    python tests/benchmark_key.py --cache   # reutiliza WAVs baixados antes

Saída:
    Tabela: perfil x música, acerto/erro, sugestão de calibração.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import essentia.standard as es
from pipeline import detect_tuning, download_audio, key_to_camelot

# ---------------------------------------------------------------------------
# Músicas com tonalidade documentada por múltiplas fontes
# Fontes de referência: Tunebat, AllMusic, Song Key Finder, tablaturas oficiais
# ---------------------------------------------------------------------------
class TestCase(NamedTuple):
    name: str
    url: str
    expected: str   # ex: "F# minor"
    camelot: str    # ex: "11A" — calculado de expected, usado para comparação

_RAW_CASES: list[tuple[str, str, str]] = [
    # (nome, url, expected_key)

    # --- Pop / R&B ---
    ("Billie Jean — Michael Jackson",
     "https://www.youtube.com/watch?v=Zi_XLOBDo_Y",
     "F# minor"),       # 11A — consenso de todas as ferramentas

    ("Blinding Lights — The Weeknd",
     "https://www.youtube.com/watch?v=4NRXx6U8ABQ",
     "F minor"),        # 4A

    ("Bad Guy — Billie Eilish",
     "https://www.youtube.com/watch?v=DyDfgMOUjCI",
     "G minor"),        # 6A

    ("Shape of You — Ed Sheeran",
     "https://www.youtube.com/watch?v=JGwWNGJdvx8",
     "C# minor"),       # 12A (relativa: A major)

    # --- Hip-hop / Trap ---
    ("Hotline Bling — Drake",
     "https://www.youtube.com/watch?v=uxpDa-c-4Mc",
     "D minor"),        # 7A

    ("HUMBLE. — Kendrick Lamar",
     "https://www.youtube.com/watch?v=tvTRZJ-4EyI",
     "G minor"),        # 6A

    ("Lucid Dreams — Juice WRLD",
     "https://www.youtube.com/watch?v=mzB1VGEGcSU",
     "G minor"),        # 6A

    ("XO Tour Llif3 — Lil Uzi Vert",
     "https://www.youtube.com/watch?v=J6xJ-hfNBMk",
     "C minor"),        # 5A

    ("Mo Bamba — Sheck Wes",
     "https://www.youtube.com/watch?v=yPYZpwSpKmA",
     "F minor"),        # 4A

    ("Mask Off — Future",
     "https://www.youtube.com/watch?v=xvZqHgFz51I",
     "D minor"),        # 7A
]

PROFILES = ("temperley", "edma", "bgate")

TEST_CASES = [
    TestCase(name=n, url=u, expected=e, camelot=key_to_camelot(e))
    for n, u, e in _RAW_CASES
]

CACHE_DIR = Path(__file__).parent / ".wav_cache"

# ---------------------------------------------------------------------------
# Detecção isolada por perfil
# ---------------------------------------------------------------------------
def _detect_single_profile(wav_path: Path, profile: str, tuning_hz: float) -> str:
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    key, scale, _ = es.KeyExtractor(profileType=profile, tuningFrequency=tuning_hz)(audio)
    return f"{key} {scale}"


def _vote(results: dict[str, str]) -> str:
    """Mesma lógica de pipeline.detect_key: votação por código Camelot."""
    votes: dict[str, int] = {}
    best_per_code: dict[str, tuple[str, float]] = {}
    # strength não disponível aqui — usamos contagem simples
    for profile, key_str in results.items():
        code = key_to_camelot(key_str)
        votes[code] = votes.get(code, 0) + 1
        if code not in best_per_code:
            best_per_code[code] = (key_str, 0.0)

    winner = max(votes, key=lambda c: votes[c])
    return best_per_code[winner][0]


# ---------------------------------------------------------------------------
# Comparação enarmônica via Camelot
# ---------------------------------------------------------------------------
def _camelot_distance(a: str, b: str) -> int:
    """Distância em posições no Camelot wheel (0 = exato, 1 = vizinho, etc.)"""
    def _num(code: str) -> tuple[int, str]:
        return int(code[:-1]), code[-1]

    if a == "?" or b == "?":
        return 99
    if a == b:
        return 0
    na, sa = _num(a)
    nb, sb = _num(b)
    if sa != sb:
        return 99  # major vs minor — erro grande
    dist = abs(na - nb)
    return min(dist, 12 - dist)


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------
def run_benchmark(keep_wavs: bool = False, use_cache: bool = True) -> None:
    CACHE_DIR.mkdir(exist_ok=True)

    # Resultados: {profile -> [acertos]}
    hits: dict[str, list[bool]] = {p: [] for p in PROFILES}
    hits["vote"] = []
    near_hits: dict[str, list[bool]] = {p: [] for p in PROFILES}
    near_hits["vote"] = []

    rows: list[dict] = []

    for tc in TEST_CASES:
        print(f"\n{'─'*60}")
        print(f"  {tc.name}")
        print(f"  Esperado: {tc.expected} ({tc.camelot})")

        wav_cache_path = CACHE_DIR / f"{tc.camelot}_{tc.name[:20].replace(' ', '_')}.wav"

        if use_cache and wav_cache_path.exists():
            wav_path = wav_cache_path
            print(f"  [cache] {wav_path.name}")
        else:
            print(f"  Baixando...")
            cache_dir = os.environ.get("YTDLP_CACHE_DIR", "")
            try:
                wav_path = download_audio(tc.url, cache_dir)
            except Exception as e:
                print(f"  ERRO ao baixar: {e}")
                for p in PROFILES:
                    hits[p].append(False)
                    near_hits[p].append(False)
                hits["vote"].append(False)
                near_hits["vote"].append(False)
                rows.append({"name": tc.name, "expected": tc.expected,
                             **{p: "ERRO" for p in PROFILES}, "vote": "ERRO"})
                continue

            if use_cache:
                import shutil
                shutil.copy2(wav_path, wav_cache_path)

        try:
            tuning = detect_tuning(wav_path) or 440.0
            profile_results: dict[str, str] = {}

            for profile in PROFILES:
                key_str = _detect_single_profile(wav_path, profile, tuning)
                profile_results[profile] = key_str
                code = key_to_camelot(key_str)
                dist = _camelot_distance(code, tc.camelot)
                exact = dist == 0
                near = dist <= 1
                hits[profile].append(exact)
                near_hits[profile].append(near)
                mark = "✓" if exact else ("~" if near else "✗")
                print(f"  [{profile:12s}] {key_str:15s} ({code}) {mark}")

            vote_key = _vote(profile_results)
            vote_code = key_to_camelot(vote_key)
            vote_dist = _camelot_distance(vote_code, tc.camelot)
            vote_exact = vote_dist == 0
            vote_near = vote_dist <= 1
            hits["vote"].append(vote_exact)
            near_hits["vote"].append(vote_near)
            vote_mark = "✓" if vote_exact else ("~" if vote_near else "✗")
            print(f"  [{'votação':12s}] {vote_key:15s} ({vote_code}) {vote_mark}")

            rows.append({
                "name": tc.name,
                "expected": f"{tc.expected} ({tc.camelot})",
                **{p: f"{profile_results[p]} ({key_to_camelot(profile_results[p])})" for p in PROFILES},
                "vote": f"{vote_key} ({vote_code})",
            })
        finally:
            if not keep_wavs and not use_cache and wav_path.exists():
                wav_path.unlink(missing_ok=True)

    # ---------------------------------------------------------------------------
    # Resumo de acurácia
    # ---------------------------------------------------------------------------
    total = len(TEST_CASES)
    print(f"\n{'='*60}")
    print(f"  ACURÁCIA (exata / ±1 posição Camelot)   n={total}")
    print(f"{'='*60}")

    accuracies: dict[str, float] = {}
    for key in list(PROFILES) + ["vote"]:
        n = len(hits[key])
        if n == 0:
            continue
        exact = sum(hits[key])
        near = sum(near_hits[key])
        pct_exact = exact / n * 100
        pct_near = near / n * 100
        accuracies[key] = pct_exact
        label = key if key != "vote" else "VOTAÇÃO ATUAL"
        print(f"  {label:14s}  exato={exact}/{n} ({pct_exact:.0f}%)   ±1={near}/{n} ({pct_near:.0f}%)")

    # Sugestão de calibração
    best_single = max(PROFILES, key=lambda p: accuracies.get(p, 0))
    print(f"\n  Perfil mais preciso isolado: {best_single} ({accuracies.get(best_single, 0):.0f}%)")
    print(f"  Sistema de votação:          {accuracies.get('vote', 0):.0f}%")

    if accuracies.get("vote", 0) >= max(accuracies.get(p, 0) for p in PROFILES):
        print("\n  Votação já é o melhor sistema. Nenhum ajuste necessário.")
    else:
        print(f"\n  Sugestão: dar mais peso ao perfil '{best_single}' na votação.")
        print(f"  Ver pipeline.py:detect_key para ajustar pesos.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark de key detection")
    parser.add_argument("--keep", action="store_true",
                        help="Mantém WAVs após o teste")
    parser.add_argument("--no-cache", action="store_true",
                        help="Não reutiliza WAVs do cache")
    args = parser.parse_args()

    run_benchmark(keep_wavs=args.keep, use_cache=not args.no_cache)
