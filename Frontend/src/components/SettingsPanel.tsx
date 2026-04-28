import { themeOptions, type ThemeId } from "../theme";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  theme: ThemeId;
  onThemeChange: (theme: ThemeId) => void;
}

const SettingsPanel = ({ isOpen, onClose, theme, onThemeChange }: SettingsPanelProps) => {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="settings-overlay" role="dialog" aria-modal="true">
      <div className="settings-panel">
        <header className="settings-header">
          <h2>Workspace Settings</h2>
          <button className="ghost-button" onClick={onClose}>
            Close
          </button>
        </header>
        <section className="settings-section">
          <h3>Appearance</h3>
          <label className="settings-field theme-picker">
            <span>Theme</span>
            <select
              className="theme-select"
              value={theme}
              onChange={(event) => onThemeChange(event.target.value as ThemeId)}
            >
              {themeOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </section>
        <section className="settings-section">
          <h3>Session</h3>
          <label className="settings-field">
            <span>API Base URL</span>
            <input type="text" placeholder="https://api.example.com" />
          </label>
          <label className="settings-field">
            <span>API Key</span>
            <input type="password" placeholder="••••••••" />
          </label>
        </section>
        <section className="settings-section">
          <h3>Conversation</h3>
          <label className="settings-field">
            <span>Temperature</span>
            <input type="number" min="0" max="1" step="0.1" defaultValue={0.2} />
          </label>
          <label className="settings-field">
            <span>Max Turns</span>
            <input type="number" min="1" max="20" defaultValue={6} />
          </label>
        </section>
      </div>
    </div>
  );
};

export default SettingsPanel;
