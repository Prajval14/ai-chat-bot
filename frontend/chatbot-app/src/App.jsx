import React from "react";
import Chatbot from "./Chatbot";

const BOT_NAME = import.meta.env.VITE_BOT_NAME;
const BOT_ICON = import.meta.env.VITE_BOT_ICON;
const BOT_COLOR = import.meta.env.VITE_BOT_COLOR;

function App() {
  return (
    <div>
      <Chatbot botName={BOT_NAME} botIcon={"https://thumbs.dreamstime.com/b/robot-icon-chat-bot-sign-support-service-concept-chatbot-character-flat-style-robot-icon-chat-bot-sign-support-service-121644324.jpg"} botColor={BOT_COLOR} />
    </div>
  );
}

export default App;