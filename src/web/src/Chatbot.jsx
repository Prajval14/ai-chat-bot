import React, { useRef, useEffect, useState } from "react";
import "./Chatbot.css";
import { FaRobot, FaTimes, FaComments, FaChevronDown } from "react-icons/fa";

export default function Chatbot({ botName, botIcon, botColor }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      from: "bot",
      text: `Hey! I'm ${botName}, your personal MadeWithNestlé assistant. Ask me anything, and I'll quickly search the entire site to find the answers you need!`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);
  const apiBase = "https://app-botdevone-api.azurewebsites.net"  //Change this url to your backend endpoint

  useEffect(() => {
    if (open && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages, loading, open]);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [loading, open]);

  function formatMessage(text) {
    let formatted = text.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    formatted = formatted.replace(
      /(?<!["'>])\bhttps?:\/\/[^\s)<]+/g,
      '<a href="$&" target="_blank" rel="noopener noreferrer">here</a>'
    );
    formatted = formatted.replace(/\s?\(<a[^)]+<\/a>\)/g, match => match.replace(/[()]/g, ''));
    return formatted;
  }

  // Handle sending message
  async function sendMessage() {
    if (!input.trim()) return;
    const userMsg = input;
    const nextMessages = [...messages, { from: "user", text: userMsg }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg }),
      });

      let botMsg = "Error: Could not connect to backend.";
      if (response.ok) {
        const data = await response.json();
        botMsg = data.answer;
      }
      const updatedMsgs = [...nextMessages, { from: "bot", text: botMsg }];
      setMessages(updatedMsgs);
    } catch (err) {
      console.log(err)
      const updatedMsgs = [
        ...nextMessages,
        { from: "bot", text: "Error: Could not connect to backend." },
      ];
      setMessages(updatedMsgs);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatbot-floating">
      <button
        className="chatbot-toggle"
        style={{ background: botColor }}
        onClick={() => setOpen((prev) => !prev)}
        aria-label={open ? "Close chat" : "Open chat"}
      >
        {open ? <FaTimes size={28} /> : <FaComments size={28} />}
      </button>
      <div className={`chatbot-window ${open ? "open" : ""}`}>
        <div className="chatbot-header" style={{ background: botColor }}>
          <div className="chatbot-header-info">
            {botIcon ? (
              <img src={botIcon} alt="bot" className="chatbot-header-icon" />
            ) : (
              <FaRobot size={32} color="#fff" />
            )}
            <span>{botName}</span>
          </div>
          <button
            className="chatbot-header-close"
            onClick={() => setOpen(false)}
          >
            <FaChevronDown size={20} />
          </button>
        </div>
        <div className="chatbot-body" ref={bodyRef}>
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`chatbot-message ${msg.from}`}
              style={
                msg.from === "user"
                  ? { background: botColor, color: "#fff" }
                  : {}
              }
            >
              {msg.from === "bot" ? (
                <span dangerouslySetInnerHTML={{ __html: formatMessage(msg.text) }} />
              ) : (
                msg.text
              )}
            </div>
          ))}
          {loading && <div className="chatbot-message bot">Thinking...</div>}
        </div>
        <div className="chatbot-footer">
          <textarea
            ref={inputRef}
            type="text"
            placeholder="Ask me anything..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            disabled={loading}
            autoFocus={open}
            rows={1}
          />
          <button
            className="chatbot-send"
            style={{
              background: botColor,
              cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            }}
            onClick={sendMessage}
            disabled={loading || !input.trim()}
          >
            <span>↑</span>
          </button>
        </div>
      </div>
    </div>
  );
}
