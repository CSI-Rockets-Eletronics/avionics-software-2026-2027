#!/usr/bin/env node

/**
 * PreToolUse hook to protect specific files from unauthorized edits.
 *
 * Protected files and their allowed edits (per CLAUDE.md):
 * - main/devices/dev_cap_fill.h: NO EDITS ALLOWED
 * - main/devices/dev_ereg_control.h: ONLY allowed edit is kServoPin 9 → 42 in Phase 5
 * - main/devices/dev_fs_relays.h: ONLY allowed edits in Phase 4:
 *     (a) RelayPin values → constants from fs_board_config.h
 *     (b) SendState() rate limiting
 */

const fs = require('fs');
const path = require('path');

// Read the tool use from stdin
const stdin = fs.readFileSync(0, 'utf-8');
let toolUse;

try {
  toolUse = JSON.parse(stdin);
} catch (e) {
  console.error('Failed to parse tool use JSON');
  process.exit(1);
}

// Protected files configuration
const PROTECTED_FILES = {
  'main/devices/dev_cap_fill.h': {
    allowed: false,
    message: 'dev_cap_fill.h: NO EDITS ALLOWED per CLAUDE.md'
  },
  'main/devices/dev_ereg_control.h': {
    allowed: 'conditional',
    message: 'dev_ereg_control.h: ONLY allowed edit is kServoPin 9 → 42 in Phase 5. For anything else, STOP and ask.',
    checkEdit: (old_string, new_string) => {
      // Allow the specific kServoPin edit
      if (old_string.includes('kServoPin') && old_string.includes('9') &&
          new_string.includes('kServoPin') && new_string.includes('42')) {
        return true;
      }
      return false;
    }
  },
  'main/devices/dev_fs_relays.h': {
    allowed: 'conditional',
    message: 'dev_fs_relays.h: ONLY allowed edits in Phase 4: (a) RelayPin values → fs_board_config.h constants, (b) SendState() rate limiting. For anything else, STOP and ask.',
    checkEdit: (old_string, new_string) => {
      // Allow RelayPin changes to fs_board_config.h constants
      if (old_string.includes('RelayPin') || new_string.includes('fs_board_config.h')) {
        return true;
      }
      // Allow SendState() rate limiting changes
      if (old_string.includes('SendState') || new_string.includes('SendState')) {
        return true;
      }
      return false;
    }
  }
};

// Check if this is an Edit or Write tool use
if (toolUse.name === 'Edit' || toolUse.name === 'Write') {
  const filePath = toolUse.params?.file_path || '';

  // Normalize path separators for comparison
  const normalizedPath = filePath.replace(/\\/g, '/');

  // Check each protected file
  for (const [protectedPath, config] of Object.entries(PROTECTED_FILES)) {
    if (normalizedPath.includes(protectedPath)) {

      if (config.allowed === false) {
        // Completely blocked
        console.error(`\n❌ BLOCKED: ${config.message}\n`);
        process.exit(1);
      }
      else if (config.allowed === 'conditional' && toolUse.name === 'Edit') {
        // Check if the specific edit is allowed
        const old_string = toolUse.params?.old_string || '';
        const new_string = toolUse.params?.new_string || '';

        if (!config.checkEdit(old_string, new_string)) {
          console.error(`\n❌ BLOCKED: ${config.message}\n`);
          console.error(`Attempted edit not in the approved list.\n`);
          process.exit(1);
        } else {
          console.log(`\n✅ Approved edit to ${protectedPath}\n`);
        }
      }
      else if (config.allowed === 'conditional' && toolUse.name === 'Write') {
        // Write operations are blocked on conditional files
        console.error(`\n❌ BLOCKED: ${config.message}\n`);
        console.error(`Write operation not allowed. Use Edit instead.\n`);
        process.exit(1);
      }
    }
  }
}

// If we get here, the tool use is allowed
process.exit(0);
