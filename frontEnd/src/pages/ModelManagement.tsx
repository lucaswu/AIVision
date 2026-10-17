import { Card, Table, Tag, Typography, Descriptions, Button, Space, Empty } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { modelStatusAPI } from "@/utils/api";

const { Title, Text } = Typography;

const SLOT_LABELS: Record<string, string> = {
  primary: "主检测模型",
  roi: "ROI 模型",
  location_0: "定位模型 0",
  location_1: "定位模型 1",
};

export default function ModelManagement() {
  const { data: status, loading, refresh } = useRequest(() =>
    modelStatusAPI.getSilently()
  );

  const rows = Object.entries<any>(status?.profile_details || {}).flatMap(
    ([profile, detail]) =>
      Object.entries<any>(detail?.slots || {}).map(([slot, info]) => ({
        key: `${profile}/${slot}`,
        profile,
        slot,
        warmed: detail?.warmed,
        ...info,
      }))
  );

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>模型管理</Title>
          <Text type="secondary">推理服务当前激活的模型组合（只读）</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
          刷新
        </Button>
      </Space>

      {!status && !loading ? (
        <Card style={{ marginTop: 24 }}>
          <Empty description="无法获取推理服务状态，请检查 ai-inference 是否正常运行" />
        </Card>
      ) : (
        <>
          <Card style={{ marginTop: 24 }} loading={loading}>
            <Descriptions column={3} size="small">
              <Descriptions.Item label="运行状态">
                <Tag color={status?.runtime_state === "active" ? "green" : "orange"}>
                  {status?.runtime_state}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="模型组合 ID">{status?.set_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="代数">{status?.generation ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="推理服务版本">{status?.inference_version || "-"}</Descriptions.Item>
              <Descriptions.Item label="GPU 空闲(MB)">{status?.gpu_free_mb ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="GPU 需求(MB)">{status?.gpu_required_mb ?? "-"}</Descriptions.Item>
            </Descriptions>
          </Card>
          <Card style={{ marginTop: 16 }}>
            <Table
              loading={loading}
              rowKey="key"
              dataSource={rows}
              pagination={false}
              columns={[
                { title: "Profile", dataIndex: "profile" },
                { title: "槽位", dataIndex: "slot", render: (s: string) => SLOT_LABELS[s] || s },
                { title: "模型名称", dataIndex: "model_name", render: (v: string) => v || <Text type="secondary">默认权重</Text> },
                { title: "权重路径", dataIndex: "relative_path" },
                { title: "Release", dataIndex: "release_id" },
                { title: "SHA256", dataIndex: "sha256", render: (v: string) => <Text code>{v?.slice(0, 12)}</Text> },
                { title: "预热", dataIndex: "warmed", render: (v: boolean) => <Tag color={v ? "green" : "default"}>{v ? "已预热" : "未预热"}</Tag> },
              ]}
            />
          </Card>
        </>
      )}
    </div>
  );
}
