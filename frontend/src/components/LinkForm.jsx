import { useState, useEffect } from "react";
import { createLink, updateLink } from "../api";

export default function LinkForm({ editingLink, onSuccess }) {
  const [form, setForm] = useState({ name: "", url: "", affiliate_url: "" });

  useEffect(() => {
    if (editingLink) setForm(editingLink);
  }, [editingLink]);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (editingLink) {
      await updateLink(editingLink.id, form);
    } else {
      await createLink(form);
    }
    setForm({ name: "", url: "", affiliate_url: "" });
    onSuccess();
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>{editingLink ? "Sửa link" : "Thêm link mới"}</h2>
      <input
        name="name"
        value={form.name}
        onChange={handleChange}
        placeholder="Tên"
        required
      />
      <input
        name="url"
        value={form.url}
        onChange={handleChange}
        placeholder="URL gốc"
        required
      />
      <input
        name="affiliate_url"
        value={form.affiliate_url}
        onChange={handleChange}
        placeholder="Affiliate URL"
        required
      />
      <button type="submit">{editingLink ? "Cập nhật" : "Thêm"}</button>
    </form>
  );
}
