import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function BotConfigSettings({ apiBase, botConfig, onConfigUpdated }) {
  const [form, setForm] = useState(botConfig);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setForm(botConfig);
  }, [botConfig]);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/bot-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        alert("Bot configuration updated!");
        if (typeof onConfigUpdated === "function") onConfigUpdated();
        navigate("/");
      } 
      // else {
      //   alert("Failed to update config. Please try again.");
      // }
    } catch (err) {
      console.log(err)
      alert("Network error. Please try again.");
    }
    setSaving(false);
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        margin: "2rem auto",
        maxWidth: 340,
        background: "#fff",
        padding: 24,
        borderRadius: 16,
        boxShadow: "0 2px 14px rgba(80,0,150,0.10)",
      }}
    >
      <h2 style={{ marginBottom: 16, color: "#7c3aed" }}>Bot Configuration</h2>
      <label>
        Name:<br />
        <input
          name="bot_name"
          value={form.bot_name}
          onChange={handleChange}
          style={{
            width: "100%",
            marginBottom: 12,
            padding: 8,
            borderRadius: 6,
            border: "1px solid #eee",
          }}
        />
      </label>
      <label>
        Icon URL:<br />
        <input
          name="bot_icon"
          value={form.bot_icon}
          onChange={handleChange}
          placeholder="Paste image URL or leave blank for default"
          style={{
            width: "100%",
            marginBottom: 12,
            padding: 8,
            borderRadius: 6,
            border: "1px solid #eee",
          }}
        />
      </label>
      <label>
        Color:<br />
        <input
          name="bot_color"
          value={form.bot_color}
          type="color"
          onChange={handleChange}
          style={{
            width: 60,
            height: 34,
            marginBottom: 16,
            padding: 0,
            border: "none",
          }}
        />
      </label>
      <br />
      <button
        type="submit"
        disabled={saving}
        style={{
          background: "#7c3aed",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          padding: "8px 20px",
          cursor: saving ? "not-allowed" : "pointer",
          fontWeight: "bold",
          fontSize: "1rem",
        }}
      >
        {saving ? "Saving..." : "Save"}
      </button>
    </form>
  );
}