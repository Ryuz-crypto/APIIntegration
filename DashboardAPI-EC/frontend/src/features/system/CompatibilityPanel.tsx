import { Box, Paper, Stack, Typography } from "@mui/material";
import { StatusChip } from "../../components/StatusChip";
import { CompatibilityProfile } from "../../lib/api";

export function CompatibilityPanel({ profiles }: { profiles: CompatibilityProfile[] }) {
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h2" sx={{ mb: 2 }}>
        API Compatibility
      </Typography>
      <Stack spacing={1.25}>
        {profiles.map((profile) => (
          <Box
            key={profile.version}
            sx={{
              display: "grid",
              gridTemplateColumns: "70px 110px 1fr",
              alignItems: "center",
              gap: 1
            }}
          >
            <Typography fontWeight={700}>{profile.version}</Typography>
            <StatusChip status={profile.status} />
            <Typography variant="body2" color="text.secondary">
              {profile.operations.length} operations
            </Typography>
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}
