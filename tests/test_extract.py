"""extract モジュールの単体テスト。"""

from __future__ import annotations

from localllm_feed import extract


def test_extract_params_b_basic() -> None:
    assert extract.extract_params_b("Command-R-35B-v0.1-GGUF") == 35.0
    assert extract.extract_params_b("Llama-3-8B-Instruct") == 8.0
    assert extract.extract_params_b("Phi-3.8B") == 3.8


def test_extract_params_b_picks_max() -> None:
    assert extract.extract_params_b("mix-7B-to-13B") == 13.0


def test_extract_params_b_moe_uses_expert_size() -> None:
    # MoE 表記はエキスパート数ではなく各エキスパートのパラメータ数を名目値とする
    assert extract.extract_params_b("Mixtral-8x7B-Instruct-GGUF") == 7.0
    assert extract.extract_params_b("Mixtral-8x22B") == 22.0


def test_extract_params_b_none_when_absent() -> None:
    assert extract.extract_params_b("SomeModel-GGUF") is None
    assert extract.extract_params_b("") is None


def test_extract_quants_dedup_and_order() -> None:
    files = [
        "model-Q4_K_M.gguf",
        "model-Q8_0.gguf",
        "model-Q4_K_M.gguf",
        "model-IQ4_XS.gguf",
    ]
    assert extract.extract_quants(files) == ["Q4_K_M", "Q8_0", "IQ4_XS"]


def test_extract_quants_ignores_non_gguf() -> None:
    # 非 GGUF ファイル名（config-Q4.json 等）は量子化として拾わない
    files = ["config-Q4.json", "README.md", "model-Q5_K_M.gguf"]
    assert extract.extract_quants(files) == ["Q5_K_M"]


def test_is_distilled() -> None:
    assert extract.is_distilled("DeepSeek-R1-Distill-Qwen-7B") is True
    assert extract.is_distilled("Qwen2-7B", tags=["distillation"]) is True
    assert extract.is_distilled("Qwen2-7B") is False


def test_normalize_base_strips_gguf() -> None:
    assert extract.normalize_base("Command-R-35B-GGUF") == "Command-R-35B"
    assert extract.normalize_base("Llama-3-8B") == "Llama-3-8B"
