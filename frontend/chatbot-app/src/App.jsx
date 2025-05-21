import React from "react";
import Chatbot from "./Chatbot";

// Get values directly from the environment
const BOT_NAME = import.meta.env.VITE_BOT_NAME;
const BOT_ICON = import.meta.env.VITE_BOT_ICON;
const BOT_COLOR = import.meta.env.VITE_BOT_COLOR;

function App() {
  return (
    <div>
      <Chatbot botName={BOT_NAME} botIcon={BOT_ICON} botColor={BOT_COLOR} />
    </div>
  );
}

export default App;