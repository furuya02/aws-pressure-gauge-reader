/**
 * Bedrock Agent用のOpenAPI Schema定義
 * 圧力計ゲージ針検出API
 */

export const gaugeDetectionSchema = {
  openapi: '3.0.0',
  info: {
    title: 'Pressure Gauge Detection API',
    version: '1.0.0',
    description: 'API for detecting and highlighting pressure gauge needles using YOLO segmentation'
  },
  paths: {
    '/detect-gauge': {
      post: {
        summary: 'Detect and highlight pressure gauge needle',
        description: 'Processes a pressure gauge image, detects the needle using YOLO, and returns an image with the needle highlighted with red overlay and red triangle marker',
        operationId: 'detectGaugeNeedle',
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['image'],
                properties: {
                  image: {
                    type: 'string',
                    description: 'Base64 encoded pressure gauge image (PNG, JPEG, etc.)',
                    example: 'iVBORw0KGgoAAAANSUhEUgAA...'
                  }
                }
              }
            }
          }
        },
        responses: {
          '200': {
            description: 'Successfully processed the gauge image',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    processedImage: {
                      type: 'string',
                      description: 'Base64 encoded processed image with highlighted needle'
                    },
                    message: {
                      type: 'string',
                      description: 'Processing status message',
                      example: '処理成功'
                    }
                  }
                }
              }
            }
          },
          '400': {
            description: 'Bad request - missing required parameters',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    error: {
                      type: 'string',
                      description: 'Error message'
                    }
                  }
                }
              }
            }
          },
          '500': {
            description: 'Internal server error during processing',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    error: {
                      type: 'string',
                      description: 'Error message'
                    },
                    type: {
                      type: 'string',
                      description: 'Error type'
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
};
