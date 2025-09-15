#!/usr/bin/env python3
"""
Generate shareable beta testing links for easy distribution
"""
import argparse
import urllib.parse
import sys
from datetime import datetime

def generate_beta_link(
    pr_number=None,
    pr_branch="main",
    pr_commit=None,
    api_key=None,
    ncbi_key=None,
    email=None,
    port=8000,
    tag="beta-latest",
    base_url="http://localhost:8000"
):
    """
    Generate a shareable beta testing link
    """
    params = {}
    
    if pr_number:
        params["pr"] = pr_number
    if pr_branch:
        params["branch"] = pr_branch
    if pr_commit:
        params["commit"] = pr_commit
    if api_key:
        params["apiKey"] = api_key
    if ncbi_key:
        params["ncbiKey"] = ncbi_key
    if email:
        params["email"] = email
    if port != 8000:
        params["port"] = port
    if tag != "beta-latest":
        params["tag"] = tag
    
    # Generate the URL
    query_string = urllib.parse.urlencode(params)
    beta_url = f"{base_url}/beta-deploy.html?{query_string}"
    
    return beta_url

def generate_docker_commands(
    pr_number=None,
    tag="beta-latest",
    port=8000,
    api_key=None,
    ncbi_key=None,
    email=None
):
    """
    Generate Docker commands for easy copy-paste
    """
    container_name = f"bioanalyzer-beta-{pr_number or 'manual'}"
    
    commands = []
    commands.append("# BioAnalyzer Beta Testing Commands")
    commands.append("# Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    commands.append("")
    
    # Stop existing container
    commands.append("# Stop existing container (if any)")
    commands.append(f"docker stop {container_name} 2>/dev/null || true")
    commands.append(f"docker rm {container_name} 2>/dev/null || true")
    commands.append("")
    
    # Pull and run
    commands.append("# Pull and run the beta image")
    commands.append(f"docker run -d \\")
    commands.append(f"  --name {container_name} \\")
    commands.append(f"  -p {port}:8000 \\")
    
    if api_key:
        commands.append(f"  -e GEMINI_API_KEY=***REDACTED*** \\")
    if ncbi_key:
        commands.append(f"  -e NCBI_API_KEY=***REDACTED*** \\")
    if email:
        commands.append(f"  -e EMAIL=***REDACTED*** \\")
    
    commands.append(f"  ghcr.io/your-username/bioanalyzer:{tag}")
    commands.append("")
    
    # URLs
    commands.append("# Access URLs")
    commands.append(f"echo 'Frontend: http://localhost:{port}'")
    commands.append(f"echo 'API: http://localhost:{port}/api'")
    commands.append(f"echo 'Docs: http://localhost:{port}/docs'")
    commands.append(f"echo 'Health: http://localhost:{port}/health'")
    commands.append("")
    
    # Management commands
    commands.append("# Management commands")
    commands.append(f"# View logs: docker logs -f {container_name}")
    commands.append(f"# Stop: docker stop {container_name}")
    commands.append(f"# Remove: docker rm {container_name}")
    
    return "\n".join(commands)

def main():
    parser = argparse.ArgumentParser(description="Generate shareable beta testing links")
    
    # PR information
    parser.add_argument("--pr", type=int, help="PR number")
    parser.add_argument("--branch", default="main", help="Branch name")
    parser.add_argument("--commit", help="Commit SHA")
    
    # API keys
    parser.add_argument("--api-key", help="Gemini API key")
    parser.add_argument("--ncbi-key", help="NCBI API key")
    parser.add_argument("--email", help="Email address")
    
    # Configuration
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--tag", default="beta-latest", help="Docker image tag")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL")
    
    # Output options
    parser.add_argument("--output", choices=["url", "commands", "both"], default="both", 
                       help="Output format")
    parser.add_argument("--file", help="Save output to file")
    
    args = parser.parse_args()
    
    # Generate beta link
    beta_url = generate_beta_link(
        pr_number=args.pr,
        pr_branch=args.branch,
        pr_commit=args.commit,
        api_key=args.api_key,
        ncbi_key=args.ncbi_key,
        email=args.email,
        port=args.port,
        tag=args.tag,
        base_url=args.base_url
    )
    
    # Generate Docker commands
    docker_commands = generate_docker_commands(
        pr_number=args.pr,
        tag=args.tag,
        port=args.port,
        api_key=args.api_key,
        ncbi_key=args.ncbi_key,
        email=args.email
    )
    
    # Prepare output
    output_lines = []
    
    if args.output in ["url", "both"]:
        output_lines.append("🔗 Beta Testing Link:")
        output_lines.append(beta_url)
        output_lines.append("")
    
    if args.output in ["commands", "both"]:
        output_lines.append("🐳 Docker Commands:")
        output_lines.append(docker_commands)
    
    output = "\n".join(output_lines)
    
    # Output to file or stdout
    if args.file:
        with open(args.file, "w") as f:
            f.write(output)
        print(f"✅ Output saved to {args.file}")
    else:
        print(output)

if __name__ == "__main__":
    main()
