// frontend/src/components/OfferList.jsx
import { useEffect, useState, useCallback } from "react";
import { getOffers } from "../api";
import {
  Paper, Typography, Box, TextField, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, useMediaQuery, Card, CardContent, Button, Stack, Chip,
  Pagination, CircularProgress, IconButton
} from "@mui/material";
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import RefreshIcon from '@mui/icons-material/Refresh';

const DEFAULT_PAGE_SIZE = 20;

function OfferCard({ o }) {
  return (
    <Card variant="outlined" sx={{ display:'flex', flexDirection:'column', height:'100%' }}>
      <CardContent sx={{ display:'flex', flexDirection:'column', gap:0.75 }}>
        <Typography variant="subtitle2" sx={{ fontWeight:600, lineHeight:1.3 }}>
          {o.title || '(Không tiêu đề)'}
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {o.merchant && <Chip size="small" label={o.merchant} />}
          {o.price && <Chip size="small" color="primary" variant="outlined" label={`${o.price} ${o.currency || 'VND'}`} />}
          {o.approval_status && <Chip size="small" variant="outlined" label={o.approval_status} />}
        </Stack>
        <Button size="small" component="a" href={(o.affiliate_url || o.url)} target="_blank" rel="noreferrer" endIcon={<OpenInNewIcon fontSize="inherit" />}>Mở</Button>
      </CardContent>
    </Card>
  );
}

export default function OfferList() {
  const [offers, setOffers] = useState([]);
  const [merchant, setMerchant] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE); // fixed page size (remove setter to satisfy no-unused-vars)
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [totalApprox, setTotalApprox] = useState(null); // backend chưa trả total -> có thể ước lượng
  const isMobile = useMediaQuery(theme => theme.breakpoints.down('sm'));

  const load = useCallback(async ({ page: p=page, merchant: m=merchant } = {}) => {
    setLoading(true); setError(null);
    try {
      const res = await getOffers({ merchant: m?.trim()||undefined, page: p, pageSize });
      setOffers(res.data || []);
      // Nếu trả về ít hơn pageSize và không phải trang 1 => có thể là trang cuối
      if ((res.data||[]).length < pageSize) {
        // Ước lượng total tối thiểu
        setTotalApprox((p-1)*pageSize + (res.data||[]).length);
      }
    } catch (e) {
      setError(e?.normalized?.message || 'Lỗi tải danh sách');
    } finally { setLoading(false); }
  }, [merchant, page, pageSize]);

  useEffect(() => { load({ page:1 }); /* initial */ }, [load]);

  const onSearch = () => { setPage(1); load({ page:1, merchant }); };
  const onChangePage = (_e, value) => { setPage(value); load({ page:value }); };

  const content = (
    <>
      {isMobile ? (
        <Box sx={{ display:'grid', gap:1.5, gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))' }}>
          {offers.map(o => <OfferCard key={o.id} o={o} />)}
          {!loading && offers.length === 0 && <Typography variant="body2" sx={{ opacity:0.7 }}>Chưa có sản phẩm</Typography>}
        </Box>
      ) : (
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
                    <a href={(o.affiliate_url || o.url)} target="_blank" rel="noreferrer">Mở sản phẩm</a>
                  </TableCell>
                </TableRow>
              ))}
              {!loading && offers.length === 0 && (<TableRow><TableCell colSpan={4}>Chưa có sản phẩm</TableCell></TableRow>)}
              {loading && offers.length === 0 && (
                <TableRow><TableCell colSpan={4} align="center"><CircularProgress size={28} /></TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <Box sx={{ display:'flex', justifyContent:'space-between', alignItems:'center', mt:2, flexWrap:'wrap', gap:1 }}>
        <Pagination
          size={isMobile? 'small':'medium'}
          page={page}
          onChange={onChangePage}
          count={ (totalApprox ? Math.max(page, Math.ceil(totalApprox / pageSize)) : (offers.length < pageSize ? page : page + 1)) }
          showFirstButton={!isMobile}
          showLastButton={!isMobile}
        />
        <Typography variant="caption" sx={{ opacity:0.7 }}>
          Trang {page}{totalApprox ? ` / ~${Math.ceil(totalApprox / pageSize)}`: ''} – {offers.length} mục
        </Typography>
      </Box>
    </>
  );

  return (
    <Paper sx={{ p: 2, mt: 3 }}>
      <Box sx={{ display:'flex', alignItems:'center', gap:1, mb:2, flexWrap:'wrap' }}>
        <Typography variant="h6" gutterBottom sx={{ flexGrow:1 }}>Danh mục sản phẩm (từ DB)</Typography>
        <IconButton aria-label="refresh offers" onClick={()=>load({ page:1 })} disabled={loading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Box>
      <Box sx={{ display: "flex", gap: 1, mb: 2, flexWrap:'wrap' }}>
        <TextField
          label="Lọc merchant (vd: shopee, lazada, tiki)"
          size="small"
          value={merchant}
          onChange={(e) => setMerchant(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onSearch(); }}
          sx={{ minWidth:260 }}
        />
        <Button variant="contained" size="small" onClick={onSearch} disabled={loading}>Lọc</Button>
      </Box>
      {error && (
        <Paper variant="outlined" sx={{ p:1, mb:2, borderColor:'error.main', color:'error.main', fontSize:14 }}>
          {error}
        </Paper>
      )}
      {content}
    </Paper>
  );
}
