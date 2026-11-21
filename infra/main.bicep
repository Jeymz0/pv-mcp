targetScope = 'resourceGroup'

@description('Azure region. West Europe is the default for a reader in France.')
param location string = 'westeurope'

@description('Image scanned and pushed by the build workflow, including the tag or digest.')
param image string

@description('Bearer token the HTTP server requires. The same value a client sends.')
@secure()
@minLength(1)
param pvMcpToken string

@description('Optional openFDA key. An empty value leaves the anonymous quota in place.')
@secure()
param openfdaApiKey string = ''

@description('Monthly budget, in the subscription billing currency.')
@minValue(1)
param budgetAmount int = 5

@description('Address that receives the budget mail.')
param budgetContact string

@description('First day of the budget month, YYYY-MM-DD.')
param budgetStart string

param appName string = 'pv-mcp'
param environmentName string = 'cae-pv-mcp'

var apiSecret = empty(openfdaApiKey) ? [] : [
  {
    name: 'openfda-api-key'
    value: openfdaApiKey
  }
]
var apiEnv = empty(openfdaApiKey) ? [] : [
  {
    name: 'OPENFDA_API_KEY'
    secretRef: 'openfda-api-key'
  }
]

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'none'
    }
    ingressConfiguration: {
      workloadProfileName: 'Consumption'
      requestIdleTimeout: 30
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// defaultDomain is assigned when the environment exists. The compiler's type
// does not list it, so the read goes through any().
var defaultDomain = string(any(environment.properties).defaultDomain)
var hostname = '${appName}.${defaultDomain}'
var resourceUrl = 'https://${hostname}/mcp'

resource app 'Microsoft.App/containerApps@2025-07-01' = {
  name: appName
  location: location
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      secrets: concat([
        {
          name: 'pv-mcp-token'
          value: pvMcpToken
        }
      ], apiSecret)
    }
    template: {
      containers: [
        {
          name: 'pv-mcp'
          image: image
          resources: {
            cpu: any('0.25')
            memory: '0.5Gi'
          }
          env: concat([
            {
              name: 'PV_MCP_TOKEN'
              secretRef: 'pv-mcp-token'
            }
            {
              name: 'PV_MCP_HTTP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'PV_MCP_HTTP_PORT'
              value: '8000'
            }
            {
              name: 'PV_MCP_RESOURCE_URL'
              value: resourceUrl
            }
          ], apiEnv)
          probes: [
            {
              type: 'Liveness'
              tcpSocket: {
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: 'pv-mcp-monthly'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStart
    }
    notifications: {
      actual_50: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        contactEmails: [
          budgetContact
        ]
        thresholdType: 'Actual'
      }
      actual_100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: [
          budgetContact
        ]
        thresholdType: 'Actual'
      }
    }
  }
}

output url string = resourceUrl
output fqdn string = hostname
