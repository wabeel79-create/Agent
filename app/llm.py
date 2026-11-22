"""Connecteur de modèles de langage pour Kapsi-Q.

Fournisseurs :
  none        générateurs Kapsi-Q seuls (hors ligne, aucun modèle)
  ollama      modèle local gratuit (Llama 3, DeepSeek-R1, Qwen…) — les données restent sur le serveur
  groq        API compatible OpenAI (offre gratuite limitée, modèles Llama)
  openrouter  API compatible OpenAI (modèles « :free » gratuits)
  deepseek    API DeepSeek (payante, très bas coût)
  custom      tout serveur compatible OpenAI (/chat/completions)
  kapsi       modèle Kapsi : module Python exposant generate(prompt) -> str
La configuration vient de la page Réglages (base locale) puis des variables d'environnement.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import urllib.request

PRESETS = {
    "none": {"label": "Aucun (générateurs Kapsi-Q, hors ligne)", "url": "", "model": "", "cloud": False},
    "ollama": {"label": "Ollama — local et gratuit (Llama 3, DeepSeek-R1)", "url": "http://localhost:11434", "model": "llama3.1:8b", "cloud": False},
    "groq": {"label": "Groq — Llama, offre gratuite", "url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "cloud": True},
    "openrouter": {"label": "OpenRouter — modèles gratuits", "url": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-chat-v3-0324:free", "cloud": True},
    "deepseek": {"label": "DeepSeek API — bas coût", "url": "https://api.deepseek.com", "model": "deepseek-chat", "cloud": True},
    "custom": {"label": "Serveur compatible OpenAI", "url": "", "model": "", "cloud": True},
    "kapsi": {"label": "Modèle Kapsi (module Python local)", "url": "", "model": "", "cloud": False},
}

SYSTEM = ("Tu es Kapsi-Q, consultant senior en systèmes de management ISO (qualité, environnement, SST, "
          "éducation, sécurité de l'information, énergie, sécurité des aliments). Tu rédiges en français "
          "professionnel, précis et directement utilisable par un cabinet de conseil tunisien. Tu ne cites "
          "jamais le texte des normes mot pour mot ; tu reformules. Tu signales ce qui doit être vérifié.")


def _strip_think(s: str) -> str:
    return re.sub(r"<think>.*?</think>", "", s, flags=re.S).strip()


class LLM:
    def __init__(self) -> None:
        self.cfg: dict = {}
        self.configure({})

    def configure(self, saved: dict) -> None:
        prov = (saved.get("provider") or os.getenv("KAPSI_BACKEND", "none")).lower()
        if prov not in PRESETS:
            prov = "none"
        p = PRESETS[prov]
        self.cfg = {
            "provider": prov,
            "url": saved.get("url") or os.getenv("KAPSI_LLM_URL") or p["url"],
            "model": saved.get("model") or os.getenv("KAPSI_LLM_MODEL") or p["model"],
            "api_key": saved.get("api_key") or os.getenv("KAPSI_LLM_KEY", ""),
            "module": saved.get("module") or os.getenv("KAPSI_MODEL_MODULE", ""),
        }
        self.last_error = ""

    @property
    def provider(self) -> str:
        return self.cfg["provider"]

    @property
    def available(self) -> bool:
        return self.provider != "none"

    def public(self) -> dict:
        c = {k: v for k, v in self.cfg.items() if k != "api_key"}
        c["has_key"] = bool(self.cfg.get("api_key"))
        c["cloud"] = PRESETS[self.provider]["cloud"]
        return c

    def generate(self, prompt: str, max_tokens: int = 1800, timeout: int = 180) -> str | None:
        if not self.available:
            return None
        try:
            prov, url, model = self.provider, self.cfg["url"].rstrip("/"), self.cfg["model"]
            if prov == "kapsi":
                mod = importlib.import_module(self.cfg["module"])
                return _strip_think(str(mod.generate(SYSTEM + "\n\n" + prompt)))
            if prov == "ollama":
                body = {"model": model, "stream": False, "options": {"num_predict": max_tokens},
                        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
                out = self._post(url + "/api/chat", body, {}, timeout)
                return _strip_think(out["message"]["content"])
            headers = {"Authorization": f"Bearer {self.cfg['api_key']}"} if self.cfg["api_key"] else {}
            body = {"model": model, "max_tokens": max_tokens, "temperature": 0.4,
                    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
            out = self._post(url + "/chat/completions", body, headers, timeout)
            return _strip_think(out["choices"][0]["message"]["content"])
        except Exception as e:  # le logiciel reste utilisable sans modèle
            self.last_error = f"{type(e).__name__}: {e}"[:300]
            return None

    @staticmethod
    def _post(url: str, body: dict, headers: dict, timeout: int) -> dict:
        req = urllib.request.Request(url, json.dumps(body).encode(),
                                     {"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())


llm = LLM()
