import { Flex, Typography } from 'antd'
import { BRAND_LOGO_SRC, BRAND_NAME, BRAND_TAGLINE } from '../../lib/brand'

type BrandLogoProps = {
  compact?: boolean
  showTagline?: boolean
  size?: number
}

export default function BrandLogo({
  compact = false,
  showTagline = false,
  size = 34,
}: BrandLogoProps) {
  return (
    <Flex align="center" gap={10} style={{ minWidth: 0 }}>
      <img
        src={BRAND_LOGO_SRC}
        alt={`${BRAND_NAME} Logo`}
        width={size}
        height={size}
        style={{ display: 'block', flex: '0 0 auto' }}
      />
      {!compact && (
        <Flex vertical gap={0} style={{ minWidth: 0 }}>
          <Typography.Text strong style={{ fontSize: 16, lineHeight: 1.15 }}>
            {BRAND_NAME}
          </Typography.Text>
          {showTagline && (
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, lineHeight: 1.4, whiteSpace: 'nowrap' }}
            >
              {BRAND_TAGLINE}
            </Typography.Text>
          )}
        </Flex>
      )}
    </Flex>
  )
}
