#!/bin/bash
#
# WindVox Installation Script
# Installs WindVox as a systemd user service
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  WindVox Installation Script${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Detect script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Installation paths
INSTALL_DIR="$HOME/.local/share/windvox"
VENV_DIR="$INSTALL_DIR/venv"
CONFIG_DIR="$HOME/.config/windvox"
SERVICE_DIR="$HOME/.config/systemd/user"

# Check system dependencies
check_dependencies() {
    echo -e "${YELLOW}Checking system dependencies...${NC}"
    
    local missing=()
    
    # Check for required packages
    if ! dpkg -s portaudio19-dev &>/dev/null; then
        missing+=("portaudio19-dev")
    fi
    
    if ! dpkg -s python3-dev &>/dev/null; then
        missing+=("python3-dev")
    fi
    
    if ! dpkg -s python3-venv &>/dev/null; then
        missing+=("python3-venv")
    fi
    
    if ! dpkg -s python3-tk &>/dev/null; then
        missing+=("python3-tk")
    fi
    
    if ! command -v xdotool &>/dev/null; then
        missing+=("xdotool")
    fi
    
    if ! command -v xclip &>/dev/null; then
        missing+=("xclip")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${RED}Missing system dependencies:${NC}"
        for pkg in "${missing[@]}"; do
            echo "  - $pkg"
        done
        echo ""
        echo "Please install them with:"
        echo -e "${YELLOW}  sudo apt install ${missing[*]}${NC}"
        echo ""
        exit 1
    fi
    
    echo -e "${GREEN}✓ All system dependencies satisfied${NC}"
}

# Create virtual environment
create_venv() {
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    
    mkdir -p "$INSTALL_DIR"
    
    if [ -d "$VENV_DIR" ]; then
        echo "  Removing existing venv..."
        rm -rf "$VENV_DIR"
    fi
    
    python3 -m venv "$VENV_DIR"
    
    echo -e "${GREEN}✓ Virtual environment created at $VENV_DIR${NC}"
}

# Install package
install_package() {
    echo -e "${YELLOW}Installing WindVox...${NC}"
    
    # Activate venv
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install package
    pip install "$SCRIPT_DIR"
    
    deactivate
    
    echo -e "${GREEN}✓ WindVox installed${NC}"
}

# Set up configuration
setup_config() {
    echo -e "${YELLOW}Setting up configuration...${NC}"
    
    mkdir -p "$CONFIG_DIR"
    
    if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
        cp "$SCRIPT_DIR/config.yaml.example" "$CONFIG_DIR/config.yaml"
        echo -e "${GREEN}✓ Configuration template copied to $CONFIG_DIR/config.yaml${NC}"
        echo -e "${YELLOW}  ⚠ Please edit this file to add your Volcengine credentials${NC}"
    else
        echo "  Configuration file already exists, skipping..."
    fi
}

# Install systemd service
install_service() {
    echo -e "${YELLOW}Installing systemd service...${NC}"
    
    mkdir -p "$SERVICE_DIR"
    
    # Get current DISPLAY for initial setup
    CURRENT_DISPLAY="${DISPLAY:-:0}"
    
    # Create service file
    cat > "$SERVICE_DIR/windvox.service" << EOF
[Unit]
Description=WindVox Voice Input Service
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/windvox
Restart=on-failure
RestartSec=3
Environment=DISPLAY=$CURRENT_DISPLAY
Environment=XAUTHORITY=%h/.Xauthority

[Install]
WantedBy=graphical-session.target
EOF
    
    # Reload systemd
    systemctl --user daemon-reload
    
    echo -e "${GREEN}✓ Systemd service installed${NC}"
}

# Enable and start service
enable_service() {
    echo -e "${YELLOW}Enabling service...${NC}"
    
    systemctl --user enable windvox.service
    
    echo -e "${GREEN}✓ Service enabled for autostart${NC}"
}

# Main
main() {
    check_dependencies
    create_venv
    install_package
    setup_config
    install_service
    enable_service
    
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Edit your configuration:"
    echo -e "     ${YELLOW}nano $CONFIG_DIR/config.yaml${NC}"
    echo ""
    echo "  2. Add your Volcengine credentials:"
    echo "     - app_key: Your App ID"
    echo "     - access_key: Your Access Token"
    echo ""
    echo "  3. Test the connection:"
    echo -e "     ${YELLOW}$VENV_DIR/bin/windvox --test-connection${NC}"
    echo ""
    echo "  4. Start the service:"
    echo -e "     ${YELLOW}systemctl --user start windvox${NC}"
    echo ""
    echo "  5. Check status:"
    echo -e "     ${YELLOW}systemctl --user status windvox${NC}"
    echo ""
    echo "  6. View logs:"
    echo -e "     ${YELLOW}journalctl --user -u windvox -f${NC}"
    echo ""
}

main "$@"
