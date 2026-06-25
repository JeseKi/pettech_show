import { useEffect, useState, type ReactNode } from 'react'
import { Button, Space, Typography } from 'antd'
import { ArrowLeftOutlined, ArrowRightOutlined } from '@ant-design/icons'
import { AnimatePresence, motion } from 'framer-motion'

export type StepWizardStep = {
  key: string
  title: string
  content: ReactNode
  extra?: ReactNode
  nextDisabled?: boolean
  nextLabel?: string
}

type StepWizardProps = {
  steps: StepWizardStep[]
  submitButton: ReactNode
}

const stepVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 36 : -36,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? -36 : 36,
    opacity: 0,
  }),
}

export function StepWizard({ steps, submitButton }: StepWizardProps) {
  const [activeStep, setActiveStep] = useState(0)
  const [direction, setDirection] = useState(1)
  const currentStep = steps[activeStep]
  const isFirstStep = activeStep === 0
  const isLastStep = activeStep === steps.length - 1

  useEffect(() => {
    setActiveStep((current) => Math.min(current, Math.max(steps.length - 1, 0)))
  }, [steps.length])

  if (!currentStep) return null

  const goBack = () => {
    setDirection(-1)
    setActiveStep((current) => Math.max(current - 1, 0))
  }

  const goNext = () => {
    setDirection(1)
    setActiveStep((current) => Math.min(current + 1, steps.length - 1))
  }

  return (
    <div className="growth-step-wizard">
      <div className="growth-step-progress" aria-label="生成步骤">
        {steps.map((step, index) => (
          <span
            key={step.key}
            className={index === activeStep ? 'growth-step-progress-item is-active' : 'growth-step-progress-item'}
          >
            <span>{index + 1}</span>
            <small>{step.title}</small>
          </span>
        ))}
      </div>

      <div className="growth-step-viewport">
        <AnimatePresence custom={direction} mode="wait" initial={false}>
          <motion.section
            key={currentStep.key}
            custom={direction}
            variants={stepVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            className="growth-config-section growth-step-motion"
          >
            <div className="growth-step-heading">
              <div className="growth-step-title">
                <span className="growth-step-index">{activeStep + 1}</span>
                <Typography.Title level={5}>{currentStep.title}</Typography.Title>
              </div>
              {currentStep.extra}
            </div>
            {currentStep.content}
          </motion.section>
        </AnimatePresence>
      </div>

      <div className="growth-step-actions">
        <Button icon={<ArrowLeftOutlined />} disabled={isFirstStep} onClick={goBack}>
          上一步
        </Button>
        {isLastStep ? (
          submitButton
        ) : (
          <Button
            type="primary"
            icon={<ArrowRightOutlined />}
            disabled={currentStep.nextDisabled}
            onClick={goNext}
          >
            {currentStep.nextLabel ?? '下一步'}
          </Button>
        )}
      </div>

      <Space className="growth-step-current" size={6}>
        <Typography.Text type="secondary">当前步骤</Typography.Text>
        <Typography.Text>{activeStep + 1}</Typography.Text>
        <Typography.Text type="secondary">/ {steps.length}</Typography.Text>
      </Space>
    </div>
  )
}
