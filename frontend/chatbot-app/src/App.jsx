import React from "react";
import Chatbot from "./Chatbot";

console.log('VITE_BOT_NAME:', import.meta.env.VITE_BOT_NAME);
console.log('VITE_BOT_COLOR:', import.meta.env.VITE_BOT_COLOR);
console.log('VITE_BOT_ICON:', import.meta.env.VITE_BOT_ICON);
console.log('ALL ENVS:', import.meta.env);


function App() {
  const BOT_NAME = import.meta.env.VITE_BOT_NAME;
  const BOT_ICON = import.meta.env.VITE_BOT_ICON;
  const BOT_COLOR = import.meta.env.VITE_BOT_COLOR;
  return (
    <div>
      <Chatbot botName={BOT_NAME} botIcon={BOT_ICON} botColor={BOT_COLOR} />
    </div>
  );
}

export default App;