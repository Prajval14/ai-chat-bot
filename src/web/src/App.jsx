import React, { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Chatbot from "./Chatbot";
import BotConfigSettings from "./BotConfigSettings";

const API_BASE = "https://app-botdevone-api.azurewebsites.net"; //Change this url to your backend endpoint

const DEFAULT_BOT_CONFIG = {
  bot_name: "NestleBot",
  bot_icon: "",
  bot_color: "#306D51",
};

function App() {
  const [botConfig, setBotConfig] = useState(DEFAULT_BOT_CONFIG);
  const [loading, setLoading] = useState(true);

  const fetchBotConfig = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/bot-config`);
      if (res.ok) {
        const config = await res.json();
        setBotConfig({
          bot_name: config.bot_name || DEFAULT_BOT_CONFIG.bot_name,
          bot_icon: config.bot_icon ?? DEFAULT_BOT_CONFIG.bot_icon,
          bot_color: config.bot_color || DEFAULT_BOT_CONFIG.bot_color,
        });
      } else {
        setBotConfig(DEFAULT_BOT_CONFIG);
      }
    } catch (err) {
      console.log(err)
      setBotConfig(DEFAULT_BOT_CONFIG);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBotConfig();
  }, []);

  const resolvedBotIcon =
    botConfig.bot_icon && botConfig.bot_icon.trim() !== ""
      ? botConfig.bot_icon
      : DEFAULT_BOT_CONFIG.bot_icon;

  return (
    <>
      {loading ? (
        <div style={{ padding: 20, textAlign: "center" }}>Loading...</div>
      ) : (
        <Routes>
          <Route
            path="/"
            element={
              <Chatbot
                botName={botConfig.bot_name}
                botIcon={resolvedBotIcon}
                botColor={botConfig.bot_color}
              />
            }
          />
          <Route
            path="/settings"
            element={
              <BotConfigSettings
                apiBase={API_BASE}
                botConfig={botConfig}
                onConfigUpdated={fetchBotConfig}
              />
            }
          />
        </Routes>
      )}
    </>
  );
}

export default App;