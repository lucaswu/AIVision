import React, { useEffect, useMemo, useState } from "react";
import { Alert, Spin, Typography } from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import { userAPI } from "../utils/api";

const { Text } = Typography;

const sanitizeRedirect = (value: string | null) => {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/projects";
  }
  return value;
};

const SsoLogin: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [error, setError] = useState<string>();

  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);

  useEffect(() => {
    const login = async () => {
      try {
        const token = params.get("token");
        if (!token) {
          throw new Error("SSO token不能为空");
        }

        const res = await userAPI.ssoJwtLogin({ token });

        localStorage.setItem("token", res.Data.token);
        localStorage.setItem("userId", res.Data.userId);
        localStorage.setItem("username", res.Data.username);
        localStorage.setItem("role", res.Data.role);

        navigate(sanitizeRedirect(res.Data.redirect), { replace: true });
      } catch (err) {
        const message = err instanceof Error ? err.message : "SSO登录失败";
        setError(message);
      }
    };

    login();
  }, [navigate, params]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#eef5ff",
        padding: 24,
      }}
    >
      {error ? (
        <Alert
          type="error"
          showIcon
          message="单点登录失败"
          description={error}
          style={{ width: "100%", maxWidth: 520 }}
        />
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Spin />
          <Text>正在单点登录...</Text>
        </div>
      )}
    </div>
  );
};

export default SsoLogin;
