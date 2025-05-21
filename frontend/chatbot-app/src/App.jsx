import React from "react";
import Chatbot from "./Chatbot";

const BOT_NAME = import.meta.env.VITE_BOT_NAME;
const BOT_ICON = import.meta.env.VITE_BOT_ICON;
const BOT_COLOR = import.meta.env.VITE_BOT_COLOR;

function App() {
  return (
    <div>
      <Chatbot botName={"NestleBot"} botIcon={"https://www.shutterstock.com/image-vector/chat-bot-icon-virtual-smart-600nw-2478937553.jpg"} botColor={"#35775B"} />
    </div>
  );
}

export default App;