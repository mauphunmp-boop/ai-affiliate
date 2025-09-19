// frontend/src/components/OfferList.jsx
import { useEffect, useState } from "react";
import { getOffers } from "../api";
import {
  Paper, Typography, Box, TextField, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow
} from "@mui/material";

export default function OfferList() {
  const [offers, setOffers] = useState([]);
  const [merchant, setMerchant] = useState("");

  const load = async (m) => {
    const res = await getOffers(m || undefined);
    setOffers(res.data || []);
  };

  useEffect(() => { load(); }, []);

  return (
    <Paper sx={{ p: 2, mt: 3 }}>
      <Typography variant="h6" gutterBottom>Danh mục sản phẩm (từ DB)</Typography>

      <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
        <TextField
          label="Lọc theo merchant (vd: shopee, lazada, tiki)"
          size="small"
          value={merchant}
          onChange={(e) => setMerchant(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") load(merchant.trim()); }}
        />
      </Box>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Tiêu đề</TableCell>
              <TableCell>Giá</TableCell>
              <TableCell>Merchant</TableCell>
              <TableCell>Link</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {offers.map(o => (
              <TableRow key={o.id}>
                <TableCell>{o.title}</TableCell>
                <TableCell>{o.price ? `${o.price} ${o.currency || "VND"}` : "N/A"}</TableCell>
                <TableCell>{o.merchant || "-"}</TableCell>
                <TableCell>
                  <a href={(o.affiliate_url || o.url)} target="_blank" rel="noreferrer">
                    Mở sản phẩm
                  </a>
                </TableCell>
              </TableRow>
            ))}
            {offers.length === 0 && (
              <TableRow><TableCell colSpan={4}>Chưa có sản phẩm</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
