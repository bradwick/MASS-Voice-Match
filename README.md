# MASS Voice Match

A Python-based voice matching system for Home Assistant integration via HACS.

## About

MASS Voice Match is a sophisticated voice matching integration that enables advanced voice recognition and matching capabilities within Home Assistant. This project provides seamless integration with Home Assistant's automation and voice control systems.

## Features

- 🎤 Voice pattern recognition and matching
- 🔄 Seamless Home Assistant integration
- ⚡ Efficient voice processing
- 🎯 Accurate speaker identification
- 🔐 Privacy-focused local processing

## Installation

### Option 1: HACS Sideload (Recommended for Development)

Sideloading allows you to install the integration directly from this GitHub repository without waiting for official HACS listing.

#### Prerequisites
- Home Assistant installed and running
- HACS installed
- Access to your Home Assistant configuration files

#### Steps

1. **Open HACS**
   - In Home Assistant, navigate to **HACS** in the sidebar
   - Click on the three-dot menu (⋯) in the top right corner
   - Select **"Custom repositories"**

2. **Add Custom Repository**
   - Paste the repository URL: `https://github.com/bradwick/MASS-Voice-Match`
   - Select **Category**: `Integration`
   - Click **CREATE**

3. **Install the Integration**
   - You should now see "MASS Voice Match" in your HACS integrations
   - Click on it and select **"Download"**
   - Restart Home Assistant

4. **Configure the Integration**
   - Go to **Settings** → **Devices & Services**
   - Click **"Create Automation"** or search for MASS Voice Match
   - Follow the configuration flow to set up the integration

### Option 2: Manual Installation

If you prefer to install manually without HACS:

1. **Download the Integration**
   ```bash
   cd ~/.homeassistant/custom_components/
   git clone https://github.com/bradwick/MASS-Voice-Match.git mass_voice_match
   ```

2. **Restart Home Assistant**
   - Restart Home Assistant through the Settings menu
   - Or use the `homeassistant.restart` service

3. **Add to Configuration**
   - Configure through UI: **Settings** → **Devices & Services** → **Create Integration**

## Project Structure

```
MASS-Voice-Match/
├── custom_components/
│   └── mass_voice_match/
│       ├── __init__.py
│       ├── manifest.json
│       ├── strings.json
│       └── [additional integration files]
├── README.md
└── [other files]
```

## Configuration

The integration can be configured through Home Assistant's UI. Once installed, navigate to:

**Settings** → **Devices & Services** → **Integrations** → **MASS Voice Match**

### Configuration Options

- **Voice Model**: Select the voice matching model to use
- **Sensitivity**: Adjust the matching sensitivity threshold
- **Speaker Profiles**: Configure speaker identification profiles
- **Processing Mode**: Choose between local or cloud processing (if applicable)

## Usage

### Creating Voice Automations

1. Go to **Settings** → **Automations & Scenes**
2. Create a new automation
3. Set trigger to voice-based events from MASS Voice Match
4. Configure your desired actions

### Example Automation

```yaml
automation:
  - alias: "Voice Match Action"
    trigger:
      platform: voice_match
      entity_id: binary_sensor.mass_voice_match_detected
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
```

## Troubleshooting

### Integration Not Appearing in HACS

- Ensure you've added the correct repository URL
- Clear your browser cache (Ctrl+Shift+Del or Cmd+Shift+Del)
- Refresh the HACS page

### Voice Recognition Not Working

- Check that microphone permissions are granted
- Verify speaker profiles are properly configured
- Review Home Assistant logs: **Settings** → **System** → **Logs**

### Performance Issues

- Reduce the number of active voice profiles
- Adjust processing sensitivity settings
- Check system CPU and memory usage

### View Logs

Access integration logs in Home Assistant:
```
Settings → System → Logs → [search for "mass_voice_match"]
```

## Support & Issues

- 📝 **Report Issues**: [GitHub Issues](https://github.com/bradwick/MASS-Voice-Match/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/bradwick/MASS-Voice-Match/discussions)
- 📚 **Home Assistant Docs**: [Custom Components](https://developers.home-assistant.io/docs/creating_integration_manifest/)

## Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is provided as-is. While efforts are made to ensure accuracy and reliability, the authors are not responsible for any issues or damages arising from its use.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history and updates.

---

**Made with ❤️ for Home Assistant**

For more information about Home Assistant integrations, visit [home-assistant.io](https://home-assistant.io)
