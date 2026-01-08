#!/bin/bash
#
# WindVox Uninstallation Script
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}======================================${NC}"
echo -e "${YELLOW}  WindVox Uninstallation Script${NC}"
echo -e "${YELLOW}======================================${NC}"
echo ""

INSTALL_DIR="$HOME/.local/share/windvox"
CONFIG_DIR="$HOME/.config/windvox"
SERVICE_DIR="$HOME/.config/systemd/user"

# Stop and disable service
if systemctl --user is-active windvox.service &>/dev/null; then
    echo "Stopping service..."
    systemctl --user stop windvox.service
fi

if systemctl --user is-enabled windvox.service &>/dev/null; then
    echo "Disabling service..."
    systemctl --user disable windvox.service
fi

# Remove service file
if [ -f "$SERVICE_DIR/windvox.service" ]; then
    echo "Removing service file..."
    rm -f "$SERVICE_DIR/windvox.service"
    systemctl --user daemon-reload
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation directory..."
    rm -rf "$INSTALL_DIR"
fi

echo ""
echo -e "${GREEN}✓ WindVox uninstalled${NC}"
echo ""
echo "Note: Configuration files were preserved at:"
echo "  $CONFIG_DIR"
echo ""
echo "To completely remove all data, run:"
echo -e "  ${YELLOW}rm -rf $CONFIG_DIR${NC}"
echo ""
