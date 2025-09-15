"""
Beta Deployment API endpoints for easy testing
"""
import os
import subprocess
import json
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/beta", tags=["Beta Deployment"])

class DeploymentRequest(BaseModel):
    api_key: str
    ncbi_key: str
    email: str
    port: int = 8000
    tag: str = "beta-latest"
    pr_number: str = None
    pr_branch: str = None

class DeploymentStatus(BaseModel):
    status: str
    container_id: str = None
    port: int
    image_tag: str
    urls: Dict[str, str] = {}
    logs: str = ""

@router.post("/deploy", response_model=DeploymentStatus)
async def deploy_beta(
    request: DeploymentRequest,
    background_tasks: BackgroundTasks
):
    """
    Deploy a beta version of BioAnalyzer for testing
    """
    try:
        # Generate container name
        container_name = f"bioanalyzer-beta-{request.pr_number or 'manual'}"
        
        # Stop existing container if running
        await stop_container(container_name)
        
        # Start deployment in background
        background_tasks.add_task(
            deploy_container,
            container_name,
            request.port,
            request.tag,
            request.api_key,
            request.ncbi_key,
            request.email
        )
        
        return DeploymentStatus(
            status="deploying",
            port=request.port,
            image_tag=request.tag,
            urls={
                "frontend": f"http://localhost:{request.port}",
                "api": f"http://localhost:{request.port}/api",
                "docs": f"http://localhost:{request.port}/docs",
                "health": f"http://localhost:{request.port}/health"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to start beta deployment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")

@router.get("/status/{container_name}")
async def get_deployment_status(container_name: str):
    """
    Get the status of a beta deployment
    """
    try:
        # Check if container is running
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return {"status": "not_found", "message": "Container not found"}
        
        # Get container info
        info_result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True
        )
        
        if info_result.returncode == 0:
            container_info = json.loads(info_result.stdout)[0]
            port_mapping = container_info["NetworkSettings"]["Ports"]
            
            # Extract port
            port = None
            for container_port, host_ports in port_mapping.items():
                if host_ports:
                    port = host_ports[0]["HostPort"]
                    break
            
            return {
                "status": "running",
                "container_id": container_info["Id"][:12],
                "port": port,
                "image": container_info["Config"]["Image"],
                "created": container_info["Created"],
                "urls": {
                    "frontend": f"http://localhost:{port}",
                    "api": f"http://localhost:{port}/api",
                    "docs": f"http://localhost:{port}/docs",
                    "health": f"http://localhost:{port}/health"
                }
            }
        else:
            return {"status": "error", "message": "Failed to get container info"}
            
    except Exception as e:
        logger.error(f"Failed to get deployment status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.get("/logs/{container_name}")
async def get_deployment_logs(container_name: str, lines: int = 50):
    """
    Get logs from a beta deployment
    """
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container_name],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return {"error": "Failed to get logs", "message": result.stderr}
        
        return {"logs": result.stdout}
        
    except Exception as e:
        logger.error(f"Failed to get logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Log retrieval failed: {str(e)}")

@router.delete("/stop/{container_name}")
async def stop_deployment(container_name: str):
    """
    Stop and remove a beta deployment
    """
    try:
        await stop_container(container_name)
        return {"status": "stopped", "message": f"Container {container_name} stopped and removed"}
        
    except Exception as e:
        logger.error(f"Failed to stop deployment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stop failed: {str(e)}")

@router.get("/list")
async def list_deployments():
    """
    List all running beta deployments
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=bioanalyzer-beta", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return {"deployments": []}
        
        deployments = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 3:
                    deployments.append({
                        "name": parts[0],
                        "status": parts[1],
                        "ports": parts[2]
                    })
        
        return {"deployments": deployments}
        
    except Exception as e:
        logger.error(f"Failed to list deployments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")

async def stop_container(container_name: str):
    """Stop and remove a container"""
    try:
        # Stop container
        subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            timeout=10
        )
        
        # Remove container
        subprocess.run(
            ["docker", "rm", container_name],
            capture_output=True,
            timeout=10
        )
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout stopping container {container_name}")
    except Exception as e:
        logger.warning(f"Error stopping container {container_name}: {str(e)}")

async def deploy_container(
    container_name: str,
    port: int,
    tag: str,
    api_key: str,
    ncbi_key: str,
    email: str
):
    """Deploy a beta container in the background"""
    try:
        # Build the docker run command
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:8000",
            "-e", f"GEMINI_API_KEY={api_key}",
            "-e", f"NCBI_API_KEY={ncbi_key}",
            "-e", f"EMAIL={email}",
            "-e", "DEBUG=true",
            "-e", "WATCHFILES_FORCE_POLLING=true",
            f"ghcr.io/your-username/bioanalyzer:{tag}"
        ]
        
        # Run the container
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to deploy container: {result.stderr}")
        else:
            logger.info(f"Successfully deployed beta container: {container_name}")
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout deploying container {container_name}")
    except Exception as e:
        logger.error(f"Error deploying container {container_name}: {str(e)}")
