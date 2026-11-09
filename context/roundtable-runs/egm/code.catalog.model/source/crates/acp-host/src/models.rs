//! OpenRouter model selection: the current model list, never a fixed one.

use anyhow::Result;
use serde::{Deserialize, Serialize};

pub const MODELS_URL: &str = "https://openrouter.ai/api/v1/models";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenRouterModel {
    pub id: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub context_length: Option<u64>,
}

/// Fetch the published model list. The key is optional for this endpoint.
pub async fn openrouter_models(client: &reqwest::Client, api_key: Option<&str>) -> Result<Vec<OpenRouterModel>> {
    #[derive(Deserialize)]
    struct Listing {
        data: Vec<OpenRouterModel>,
    }
    let mut request = client.get(MODELS_URL);
    if let Some(key) = api_key {
        request = request.bearer_auth(key);
    }
    let listing: Listing = request.send().await?.error_for_status()?.json().await?;
    Ok(listing.data)
}
