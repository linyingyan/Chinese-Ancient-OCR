import { reactive } from "vue";

const state = reactive({
  apiKey: "",
  baseUrl: "",
  model: ""
});

export function loadLlmConfigFromStorage() {
  state.apiKey = localStorage.getItem("llm_api_key") || "";
  state.baseUrl = localStorage.getItem("llm_base_url") || "";
  state.model = localStorage.getItem("llm_model") || "";
}

export function setLlmConfigToStorage({ apiKey, baseUrl, model }) {
  localStorage.setItem("llm_api_key", apiKey || "");
  localStorage.setItem("llm_base_url", baseUrl || "");
  localStorage.setItem("llm_model", model || "");
  loadLlmConfigFromStorage();
  window.dispatchEvent(new CustomEvent("llm-config-updated"));
}

export function useLlmConfig() {
  return state;
}

