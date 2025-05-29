@description('Environment name for resource naming')
param environmentName string
@description('Location for all resources')
param location string = resourceGroup().location

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'st${environmentName}files'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {}
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  name: 'default'
  parent: storageAccount
  properties: {}
}

resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: 'files'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

// Azure AI Search
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: 'srch-${environmentName}'
  location: location
  sku: { name: 'free' }
  properties: {
    hostingMode: 'default'
    replicaCount: 1
    partitionCount: 1
  }
}

// App Service Plan (Linux)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-${environmentName}'
  location: location
  sku: {
    name: 'F1'
    tier: 'Free'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// App Service (API Backend)
resource apiAppService 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${environmentName}-api'
  location: location
  kind: 'app,linux'
  tags: {
    'azd-service-name': 'api'
  }
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
    }
  }
}


// Static Web App (Frontend)
resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: 'stapp-${environmentName}-web'
  location: location
  sku: { name: 'free' }
  tags: {
    'azd-service-name': 'web'
  }
  properties: {
    repositoryToken: ''
    buildProperties: {
      appLocation: 'src/web'
      outputLocation: 'dist'
    }
  }
}

// Outputs for azd/azure.yaml
output storageConnectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
output storageBlobContainer string = 'files'
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchKey string = listAdminKeys(searchService.id, searchService.apiVersion).primaryKey
output apiAppUrl string = 'https://${apiAppService.name}.azurewebsites.net'
output staticWebAppUrl string = staticWebApp.properties.defaultHostname