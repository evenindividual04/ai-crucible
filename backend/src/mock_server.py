"""
Mock simulation server for frontend development.

Sends realistic event sequences without calling real LLM APIs.
"""

import asyncio
from typing import Any
import random


async def send_mock_simulation(websocket: Any, prompt: str):
    """
    Send a realistic mock simulation with proper timing.
    
    This allows frontend development without API costs.
    """
    
    # Simulate thinking delay
    await asyncio.sleep(0.5)
    
    # 1. Create components
    components = [
        {"id": 1, "name": "API Gateway", "type": "service", "dependencies": []},
        {"id": 2, "name": "Auth Service", "type": "service", "dependencies": [1]},
        {"id": 3, "name": "User Database", "type": "storage", "dependencies": [2]},
        {"id": 4, "name": "Token Store", "type": "cache", "dependencies": [2]},
        {"id": 5, "name": "Load Balancer", "type": "infrastructure", "dependencies": []},
    ]
    
    for comp in components:
        await websocket.send_json({
            "type": "COMPONENT_CREATED",
            "data": comp
        })
        await asyncio.sleep(0.3)
    
    # Run 3 iterations
    for iteration in range(1, 4):
        # Iteration start
        await websocket.send_json({
            "type": "ITERATION_START",
            "data": {"iteration": iteration, "max_iterations": 3}
        })
        await asyncio.sleep(0.5)
        
        # Spawn Red Team agents
        agents = [
            {"id": f"red_1_i{iteration}", "name": "Security Hawk", "type": "RED_TEAM", "position": {"x": 100, "y": 100}},
            {"id": f"red_2_i{iteration}", "name": "Scale Monster", "type": "RED_TEAM", "position": {"x": 200, "y": 100}},
            {"id": f"red_3_i{iteration}", "name": "Cost Analyst", "type": "RED_TEAM", "position": {"x": 300, "y": 100}},
            {"id": f"red_4_i{iteration}", "name": "Logic Breaker", "type": "RED_TEAM", "position": {"x": 400, "y": 100}},
        ]
        
        for agent in agents:
            await websocket.send_json({
                "type": "AGENT_SPAWN",
                "data": agent
            })
            await asyncio.sleep(0.4)
        
        # Agents thinking
        for agent in agents:
            await websocket.send_json({
                "type": "AGENT_THINKING",
                "data": {
                    "agent_id": agent["id"],
                    "message": f"{agent['name']} analyzing system architecture..."
                }
            })
            await asyncio.sleep(0.8)
        
        # Find vulnerabilities (fewer each iteration)
        vuln_count = max(1, 4 - iteration)
        vulnerabilities = []
        
        if iteration == 1:
            vulnerabilities = [
                {
                    "id": 1,
                    "title": "JWT Signature Bypass",
                    "severity": "CRITICAL",
                    "domain": "SECURITY",
                    "component_id": 1,
                    "found_by": "red_1_i1",
                    "iteration": 1,
                    "description": "JWT tokens not properly validated"
                },
                {
                    "id": 2,
                    "title": "Rate Limit Missing",
                    "severity": "HIGH",
                    "domain": "PERFORMANCE",
                    "component_id": 1,
                    "found_by": "red_2_i1",
                    "iteration": 1,
                    "description": "No rate limiting on API endpoints"
                },
                {
                    "id": 3,
                    "title": "SQL Injection Risk",
                    "severity": "HIGH",
                    "domain": "SECURITY",
                    "component_id": 3,
                    "found_by": "red_1_i1",
                    "iteration": 1,
                    "description": "Unparameterized queries detected"
                },
                {
                    "id": 4,
                    "title": "N+1 Query Pattern",
                    "severity": "MEDIUM",
                    "domain": "COST",
                    "component_id": 3,
                    "found_by": "red_3_i1",
                    "iteration": 1,
                    "description": "Inefficient database queries"
                }
            ]
        elif iteration == 2:
            vulnerabilities = [
                {
                    "id": 5,
                    "title": "CORS Misconfiguration",
                    "severity": "MEDIUM",
                    "domain": "SECURITY",
                    "component_id": 1,
                    "found_by": "red_1_i2",
                    "iteration": 2,
                    "description": "Overly permissive CORS policy"
                },
                {
                    "id": 6,
                    "title": "Cache Stampede Risk",
                    "severity": "MEDIUM",
                    "domain": "PERFORMANCE",
                    "component_id": 4,
                    "found_by": "red_2_i2",
                    "iteration": 2,
                    "description": "No cache warming strategy"
                }
            ]
        else:
            vulnerabilities = [
                {
                    "id": 7,
                    "title": "Missing Request Timeout",
                    "severity": "LOW",
                    "domain": "CORRECTNESS",
                    "component_id": 1,
                    "found_by": "red_4_i3",
                    "iteration": 3,
                    "description": "Requests can hang indefinitely"
                }
            ]
        
        for vuln in vulnerabilities:
            await websocket.send_json({
                "type": "VULNERABILITY_FOUND",
                "data": vuln
            })
            
            # Update component risk
            risk_level = "CRITICAL" if vuln["severity"] == "CRITICAL" else \
                        "HIGH" if vuln["severity"] == "HIGH" else \
                        "MEDIUM" if vuln["severity"] == "MEDIUM" else "LOW"
            
            await websocket.send_json({
                "type": "COMPONENT_RISK_UPDATE",
                "data": {
                    "component_id": vuln["component_id"],
                    "risk_level": risk_level,
                    "vulnerability_count": 1
                }
            })
            await asyncio.sleep(1.0)
        
        # Spawn defender
        defender_type = "Architect Refactorer" if iteration == 1 else "Quick Fixer"
        await websocket.send_json({
            "type": "AGENT_SPAWN",
            "data": {
                "id": f"def_1_i{iteration}",
                "name": defender_type,
                "type": "DEFENDER",
                "position": {"x": 250, "y": 300}
            }
        })
        await asyncio.sleep(0.5)
        
        # Apply patches (patch most vulnerabilities)
        patches_to_apply = vulnerabilities[:-1] if len(vulnerabilities) > 1 else vulnerabilities
        
        for vuln in patches_to_apply:
            await websocket.send_json({
                "type": "PATCH_APPLIED",
                "data": {
                    "patch_id": vuln["id"],
                    "vulnerability_id": vuln["id"],
                    "component_id": vuln["component_id"],
                    "strategy": "REFACTOR" if iteration == 1 else "QUICK_FIX",
                    "success": True
                }
            })
            
            # Update component to safer state
            await websocket.send_json({
                "type": "COMPONENT_RISK_UPDATE",
                "data": {
                    "component_id": vuln["component_id"],
                    "risk_level": "LOW",
                    "vulnerability_count": 0
                }
            })
            await asyncio.sleep(1.2)
        
        # Calculate score (improves each iteration)
        scores = [45, 72, 88]
        grades = ["F", "C", "B"]
        risk_levels = ["CRITICAL", "MEDIUM", "LOW"]
        
        unpatched_counts = [
            {"critical": 1, "high": 2, "medium": 1, "low": 0},
            {"critical": 0, "high": 0, "medium": 2, "low": 0},
            {"critical": 0, "high": 0, "medium": 0, "low": 1}
        ]
        
        await websocket.send_json({
            "type": "SCORE_UPDATE",
            "data": {
                "score": scores[iteration - 1],
                "grade": grades[iteration - 1],
                "risk_level": risk_levels[iteration - 1],
                "delta": scores[iteration - 1] - (scores[iteration - 2] if iteration > 1 else 0),
                "unpatched": unpatched_counts[iteration - 1]
            }
        })
        await asyncio.sleep(0.5)
        
        # Judge decision
        if iteration < 3:
            await websocket.send_json({
                "type": "JUDGE_DECISION",
                "data": {
                    "decision": "CONTINUE",
                    "reason": f"{len(vulnerabilities) - len(patches_to_apply)} vulnerabilities remain unpatched"
                }
            })
        else:
            await websocket.send_json({
                "type": "JUDGE_DECISION",
                "data": {
                    "decision": "STABLE",
                    "reason": "System has reached acceptable security threshold"
                }
            })
        
        await asyncio.sleep(1.5)
    
    # Simulation end
    await websocket.send_json({
        "type": "SIMULATION_END",
        "data": {
            "score": 88,
            "grade": "B",
            "verdict": "STABLE",
            "duration_ms": 25000,
            "total_vulnerabilities": 7,
            "patched_vulnerabilities": 6
        }
    })
