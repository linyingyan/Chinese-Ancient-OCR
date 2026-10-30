import axios from "axios";
import { useLlmConfig } from "../store/llmConfig";

function getLlmHeaders() {
  const cfg = useLlmConfig();
  const apiKey = cfg.apiKey || "";
  const baseUrl = cfg.baseUrl || "";
  const model = cfg.model || "";
  const headers = {};
  if (apiKey) headers["x-llm-api-key"] = apiKey;
  if (baseUrl) headers["x-llm-base-url"] = baseUrl;
  if (model) headers["x-llm-model"] = model;
  return headers;
}

export const http = axios.create({
  baseURL: ""
});

http.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  const llmHeaders = getLlmHeaders();
  for (const [k, v] of Object.entries(llmHeaders)) {
    config.headers[k] = v;
  }
  return config;
});
