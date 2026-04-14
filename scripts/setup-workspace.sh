#!/usr/bin/env bash
# GARC setup-workspace.sh — One-shot workspace provisioning
# Sets up ~/.garc directory and Google Workspace resources

set -euo pipefail

GARC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${HOME}/.garc"

echo "GARC Workspace Setup"
echo "===================="

# Step 1: Create local directories
echo ""
echo "Step 1: Creating local directories..."
mkdir -p "${CONFIG_DIR}/cache/workspace/main/memory"
mkdir -p "${CONFIG_DIR}/cache/queue"
echo "✅ Directories created: ${CONFIG_DIR}"

# Step 2: Copy config template
echo ""
echo "Step 2: Setting up config..."
if [[ -f "${CONFIG_DIR}/config.env" ]]; then
  echo "  Config already exists: ${CONFIG_DIR}/config.env"
else
  cp "${GARC_DIR}/config/config.env.example" "${CONFIG_DIR}/config.env"
  echo "✅ Config template created: ${CONFIG_DIR}/config.env"
fi

# Step 3: Install Python dependencies
echo ""
echo "Step 3: Python dependencies..."
if command -v pip3 &>/dev/null; then
  pip3 install -q google-api-python-client google-auth-oauthlib google-auth-httplib2 pyyaml 2>/dev/null || true
  echo "✅ Python packages installed"
else
  echo "⚠️  pip3 not found. Install manually:"
  echo "   pip3 install google-api-python-client google-auth-oauthlib google-auth-httplib2 pyyaml"
fi

# Step 4: Add garc to PATH
echo ""
echo "Step 4: PATH configuration..."
GARC_BIN="${GARC_DIR}/bin"
chmod +x "${GARC_BIN}/garc"

if echo "${PATH}" | grep -q "${GARC_BIN}"; then
  echo "  ${GARC_BIN} already in PATH"
else
  echo "  Add this to your ~/.zshrc or ~/.bashrc:"
  echo ""
  echo "  export PATH=\"${GARC_BIN}:\${PATH}\""
  echo ""
  echo "  Or create a symlink:"
  echo "  ln -s ${GARC_BIN}/garc /usr/local/bin/garc"
fi

# Step 5: Google Cloud setup instructions
echo ""
echo "Step 5: Google Cloud Console setup"
echo "────────────────────────────────────"
echo ""
echo "1. Go to: https://console.cloud.google.com/"
echo "2. Create or select a project"
echo "3. Enable these APIs:"
echo "   - Google Drive API"
echo "   - Google Sheets API"
echo "   - Gmail API"
echo "   - Google Calendar API"
echo "   - Google Tasks API"
echo "   - Google Chat API (optional)"
echo ""
echo "4. Create OAuth 2.0 credentials:"
echo "   APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client IDs"
echo "   Application type: Desktop app"
echo "   Download JSON → save as ~/.garc/credentials.json"
echo ""
echo "5. Create a Google Drive folder for agent workspace"
echo "   Note the folder ID from the URL"
echo "   Example: https://drive.google.com/drive/folders/1xxxxxxxxx"
echo "                                                  ^^^^^^^^^^^^ this is the folder ID"
echo ""
echo "6. Create a Google Sheets for data storage:"
echo "   Create a new spreadsheet with these tabs:"
echo "   - memory"
echo "   - agents"
echo "   - queue"
echo "   - heartbeat"
echo "   - approval"
echo "   Note the spreadsheet ID from the URL"
echo ""
echo "7. Edit ~/.garc/config.env with your IDs:"
echo "   GARC_DRIVE_FOLDER_ID=<your folder ID>"
echo "   GARC_SHEETS_ID=<your spreadsheet ID>"
echo "   GARC_GMAIL_DEFAULT_TO=<your email>"

# Step 6: Complete
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Complete Google Cloud Console setup above"
echo "  2. Edit ~/.garc/config.env"
echo "  3. Run: garc auth login --profile backoffice_agent"
echo "  4. Run: garc init"
echo "  5. Run: garc bootstrap --agent main"
echo "  6. Run: garc status"
echo ""
echo "Try it:"
echo '  garc auth suggest "send weekly report to manager"'
