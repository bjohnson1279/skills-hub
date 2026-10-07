---
name: warehouse-slotting-sidecar-integrator
description: Manages the integration and communication between backend inventory microservices and Python FastAPI sidecars for 3D Manhattan distance calculation, time-decay seasonal velocity tracking, and warehouse slotting recommendations. Activate this skill when modifying AI/ML sidecars, spatial bin maps, or warehouse location recommendations.
---

# Warehouse Slotting Sidecar Integrator

This skill guides the integration between core domain services and specialized Python FastAPI sidecars (`python-sidecar/app/main.py`) for AI/ML-driven warehouse slotting optimization.

## When to Activate

Activate this skill when:
- Implementing or modifying 3D warehouse location grid maps (`grid_x`, `grid_y`, `grid_z`).
- Integrating seasonal velocity algorithms or travel-distance reduction calculations.
- Troubleshooting sidecar HTTP request payloads, Pydantic schemas, or date parsing.

---

## Core Principles

### 1. Spatial Bin Geometry
- Compute 3D Manhattan distance: `|x| + |y| + 2*|z|` from dispatch origin `(0,0,0)`.
- Factor in vertical z-axis height costs (picking from higher shelves takes more time/effort).

### 2. Time-Decay Seasonal Velocity
- Calculate dispatch velocity with exponential time-decay weight: `quantity * exp(-0.02 * days_ago)`.
- Ensure date parsing handles both ISO strings and naive/aware UTC datetimes cleanly.

### 3. Slotting Swap Recommendations
- Identify high-velocity items located in far bins and recommend swapping positions with low-velocity items in near bins.
- Compute travel distance savings: `velocity * distance_diff * 2`.
