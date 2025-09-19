import { useEffect, useState } from "react";
import { getLinks, deleteLink } from "../api";

export default function LinkList({ onEdit }) {
  const [links, setLinks] = useState([]);

  useEffect(() => {
    fetchLinks();
  }, []);

  const fetchLinks = async () => {
    const res = await getLinks();
    setLinks(res.data);
  };

  const handleDelete = async (id) => {
    await deleteLink(id);
    fetchLinks();
  };

  return (
    <div>
      <h2>Danh sách Affiliate Links</h2>
      <table border="1" cellPadding="6">
        <thead>
          <tr>
            <th>ID</th>
            <th>Tên</th>
            <th>URL</th>
            <th>Affiliate URL</th>
            <th>Hành động</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => (
            <tr key={link.id}>
              <td>{link.id}</td>
              <td>{link.name}</td>
              <td><a href={link.url} target="_blank" rel="noreferrer">{link.url}</a></td>
              <td><a href={link.affiliate_url} target="_blank" rel="noreferrer">{link.affiliate_url}</a></td>
              <td>
                <button onClick={() => onEdit(link)}>Sửa</button>
                <button onClick={() => handleDelete(link.id)}>Xóa</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
