import { Routes, Route, Navigate } from 'react-router-dom';
import { GalleryPage } from './pages/GalleryPage';
import { AdminGuard } from './components/AdminGuard';
import { AdminLoginPage } from './pages/AdminLoginPage';
import { AdminRoomsPage } from './pages/AdminRoomsPage';
import { AdminRoomPage } from './pages/AdminRoomPage';

export default function App() {
  return (
    <Routes>
      {/* Gallery */}
      <Route path="/" element={<GalleryPage />} />

      {/* Admin – public */}
      <Route path="/admin/login" element={<AdminLoginPage />} />

      {/* Admin – protected */}
      <Route element={<AdminGuard />}>
        <Route path="/admin" element={<Navigate to="/admin/rooms" replace />} />
        <Route path="/admin/rooms" element={<AdminRoomsPage />} />
        <Route path="/admin/rooms/:roomId" element={<AdminRoomPage />} />
      </Route>
    </Routes>
  );
}