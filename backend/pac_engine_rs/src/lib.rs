// backend/pac_engine_rs/src/lib.rs - CRITICAL FIX: Rewritten for PAC Score Calculation
use pyo3::prelude::*;
use serde_json::{json, Value};
use std::cmp::min;

/// High-performance Performance Analysis & Correction (PAC) score calculation.
#[pyfunction]
fn calculate_pac_score(metrics_json: String) -> PyResult<String> {
    
    // 1. Parse Context safely
    let metrics: Value = serde_json::from_str(&metrics_json).unwrap_or(json!({}));
    
    // 2. Safely extract and cast metrics
    let total_tasks = metrics["total_tasks"].as_i64().unwrap_or(0);
    let completed_tasks = metrics["completed_tasks"].as_i64().unwrap_or(0);
    let bug_rate = metrics["bug_rate"].as_f64().unwrap_or(0.0);
    let client_satisfaction = metrics["client_satisfaction"].as_f64().unwrap_or(0.0);

    // CRITICAL FIX 1: Completion Ratio (Weight: 40%)
    let completion_ratio: f64 = if total_tasks > 0 {
        ((completed_tasks as f64) / (total_tasks as f64)).min(1.0)
    } else {
        1.0 // Assume perfect completion if no tasks exist
    };
    
    // 2. Quality Score (Based on Bug Rate - Weight: 30%)
    let quality_score: f64 = (1.0 - (bug_rate / 100.0)).max(0.0);
    
    // 3. Client Satisfaction (Weight: 30%)
    let client_satisfaction_score: f64 = if client_satisfaction > 1.0 {
        (client_satisfaction / 100.0).min(1.0)
    } else {
        client_satisfaction.min(1.0)
    };
        
    // Calculate weighted PAC Score (out of 100)
    let pac_score: f64 = (completion_ratio * 40.0) + (quality_score * 30.0) + (client_satisfaction_score * 30.0);
    
    // CRITICAL FIX 2: Clamp final score to 0-100
    let final_pac_score: f64 = pac_score.max(0.0).min(100.0);

    // Determine Performance Tier
    let performance_tier = if final_pac_score >= 90.0 {
        "Exceeds Expectations"
    } else if final_pac_score >= 75.0 {
        "Meets Expectations"
    } else if final_pac_score >= 50.0 {
        "Needs Improvement"
    } else {
        "Critical Intervention Required"
    };
    
    // 4. Return JSON String
    let response = json!({
        "pac_score": (final_pac_score * 100.0).round() / 100.0, // Round to 2 decimal places
        "performance_tier": performance_tier,
        "accelerator": "Rust" // Audit flag for proof of acceleration
    });

    Ok(response.to_string())
}

#[pymodule]
fn pac_engine_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    // CRITICAL FIX 3: Export the new function name
    m.add_function(wrap_pyfunction!(calculate_pac_score, m)?)?; 
    Ok(())
}